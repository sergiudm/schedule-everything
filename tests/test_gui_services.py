from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from conftest import (
    TEST_CONFIG_DIR,
    TEST_DDL_PATH,
    TEST_RECORD_PATH,
    TEST_TASKS_PATH,
)


def test_status_snapshot_returns_daily_panels(monkeypatch):
    from schedule_management.gui.services import status_snapshot

    monkeypatch.setattr(
        "schedule_management.gui.services._today",
        lambda: date(2024, 2, 1),
    )

    snapshot = status_snapshot({})

    assert snapshot["config"]["rootDir"] == str(TEST_CONFIG_DIR)
    assert snapshot["config"]["activeId"] == 0
    assert snapshot["today"]["date"] == "2024-02-01"
    assert snapshot["today"]["weekday"] == "thursday"
    assert snapshot["schedule"]["isSkipped"] is False
    assert isinstance(snapshot["schedule"]["events"], list)
    assert isinstance(snapshot["tasks"], list)
    assert isinstance(snapshot["deadlines"], list)
    assert isinstance(snapshot["habits"], list)


def test_task_add_updates_existing_task_and_logs(monkeypatch, tmp_path):
    from schedule_management.gui.services import task_add

    tasks_path = tmp_path / "tasks.json"
    task_log_path = tmp_path / "tasks.log"
    tasks_path.write_text(
        json.dumps([{"description": "Draft proposal", "priority": 5}]),
        encoding="utf-8",
    )

    import schedule_management.data.loaders as loaders

    monkeypatch.setattr(loaders, "TASKS_PATH", str(tasks_path))
    monkeypatch.setattr(loaders, "TASK_LOG_PATH", str(task_log_path))
    monkeypatch.setattr("schedule_management.gui.services.TASKS_PATH", str(tasks_path))
    monkeypatch.setattr(
        "schedule_management.gui.services.TASK_LOG_PATH",
        str(task_log_path),
    )

    result = task_add({"description": "Draft proposal", "priority": 9})

    assert result["description"] == "Draft proposal"
    assert result["priority"] == 9
    assert json.loads(tasks_path.read_text(encoding="utf-8")) == [
        {"description": "Draft proposal", "priority": 9}
    ]
    log = json.loads(task_log_path.read_text(encoding="utf-8"))
    assert log[-1]["action"] == "updated"


def test_task_delete_removes_by_description(tmp_path, monkeypatch):
    from schedule_management.gui.services import task_delete

    tasks_path = tmp_path / "tasks.json"
    task_log_path = tmp_path / "tasks.log"
    tasks_path.write_text(
        json.dumps(
            [
                {"description": "Draft proposal", "priority": 9},
                {"description": "Read notes", "priority": 4},
            ]
        ),
        encoding="utf-8",
    )

    import schedule_management.data.loaders as loaders

    monkeypatch.setattr(loaders, "TASKS_PATH", str(tasks_path))
    monkeypatch.setattr(loaders, "TASK_LOG_PATH", str(task_log_path))
    monkeypatch.setattr("schedule_management.gui.services.TASKS_PATH", str(tasks_path))
    monkeypatch.setattr(
        "schedule_management.gui.services.TASK_LOG_PATH",
        str(task_log_path),
    )

    result = task_delete({"description": "Read notes"})

    assert result["deleted"] == 1
    assert json.loads(tasks_path.read_text(encoding="utf-8")) == [
        {"description": "Draft proposal", "priority": 9}
    ]


def test_deadline_add_accepts_iso_date(tmp_path, monkeypatch):
    from schedule_management.gui.services import deadline_add

    deadlines_path = tmp_path / "ddl.json"
    deadlines_path.write_text("[]", encoding="utf-8")

    import schedule_management.data.loaders as loaders

    monkeypatch.setattr(loaders, "DDL_PATH", str(deadlines_path))
    monkeypatch.setattr("schedule_management.gui.services.DDL_PATH", str(deadlines_path))

    result = deadline_add({"event": "Submit paper", "date": "2026-05-10"})

    assert result["event"] == "Submit paper"
    assert result["deadline"] == "2026-05-10"
    assert json.loads(deadlines_path.read_text(encoding="utf-8"))[0]["event"] == "Submit paper"


def test_deadline_delete_reports_missing_event(tmp_path, monkeypatch):
    from schedule_management.gui.services import GuiError, deadline_delete

    deadlines_path = tmp_path / "ddl.json"
    deadlines_path.write_text("[]", encoding="utf-8")

    import schedule_management.data.loaders as loaders

    monkeypatch.setattr(loaders, "DDL_PATH", str(deadlines_path))
    monkeypatch.setattr("schedule_management.gui.services.DDL_PATH", str(deadlines_path))

    with pytest.raises(GuiError) as exc_info:
        deadline_delete({"event": "Missing"})

    assert exc_info.value.code == "not_found"


def test_habit_mark_writes_today_record(monkeypatch, tmp_path):
    from schedule_management.gui.services import habit_mark

    record_path = tmp_path / "record.json"
    habit_path = tmp_path / "habits.toml"
    habit_path.write_text("[habits]\n1 = \"Read\"\n2 = \"Exercise\"\n", encoding="utf-8")

    import schedule_management.data.loaders as loaders

    monkeypatch.setattr(loaders, "HABIT_PATH", str(habit_path))
    monkeypatch.setattr(loaders, "RECORD_PATH", str(record_path))
    monkeypatch.setattr("schedule_management.gui.services.HABIT_PATH", str(habit_path))
    monkeypatch.setattr("schedule_management.gui.services.RECORD_PATH", str(record_path))
    monkeypatch.setattr(
        "schedule_management.gui.services._today",
        lambda: date(2026, 4, 28),
    )

    result = habit_mark({"habitIds": ["1"]})

    assert result["date"] == "2026-04-28"
    assert result["completed"] == {"1": "Read"}
    records = json.loads(record_path.read_text(encoding="utf-8"))
    assert records[0]["completed"] == {"1": "Read"}
