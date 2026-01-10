import json
from datetime import datetime
from pathlib import Path

import schedule_management.reminder_macos as reminder_macos


def test_show_habit_tracking_popup_saves_record(tmp_path, monkeypatch):
    habits_path = tmp_path / "habits.toml"
    habits_path.write_text('[habits]\n1 = "Get up early"\n2 = "Exercise"\n', encoding="utf-8")

    record_path = tmp_path / "tasks" / "record.json"
    record_path.parent.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(reminder_macos, "HABIT_PATH", str(habits_path))
    monkeypatch.setattr(reminder_macos, "RECORD_PATH", str(record_path))

    monkeypatch.setattr(
        reminder_macos,
        "choose_multiple",
        lambda options, title, prompt: [options[0]],
    )

    now = datetime(2025, 1, 2, 12, 0, 0)
    saved = reminder_macos.show_habit_tracking_popup(now=now)
    assert saved is True

    data = json.loads(record_path.read_text(encoding="utf-8"))
    assert isinstance(data, list)
    assert data[0]["date"] == "2025-01-02"
    assert data[0]["completed"] == {"1": "Get up early"}
    assert data[0]["timestamp"] == now.isoformat()

    monkeypatch.setattr(
        reminder_macos,
        "choose_multiple",
        lambda options, title, prompt: [],
    )
    saved_again = reminder_macos.show_habit_tracking_popup(now=now)
    assert saved_again is True

    data2 = json.loads(record_path.read_text(encoding="utf-8"))
    assert data2[0]["completed"] == {}


def test_show_habit_tracking_popup_cancel_does_not_save(tmp_path, monkeypatch):
    habits_path = tmp_path / "habits.toml"
    habits_path.write_text('[habits]\n1 = "Get up early"\n', encoding="utf-8")

    record_path = tmp_path / "tasks" / "record.json"
    record_path.parent.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(reminder_macos, "HABIT_PATH", str(habits_path))
    monkeypatch.setattr(reminder_macos, "RECORD_PATH", str(record_path))

    monkeypatch.setattr(reminder_macos, "choose_multiple", lambda options, title, prompt: None)

    saved = reminder_macos.show_habit_tracking_popup(now=datetime(2025, 1, 2, 12, 0, 0))
    assert saved is False
    assert not record_path.exists() or record_path.read_text(encoding="utf-8").strip() == ""

