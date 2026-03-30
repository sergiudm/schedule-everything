import json
from datetime import datetime
from pathlib import Path

import schedule_management.popups as popups


def test_show_habit_tracking_popup_saves_record(tmp_path, monkeypatch):
    habits_path = tmp_path / "habits.toml"
    habits_path.write_text(
        '[habits]\n1 = "Get up early"\n2 = "Exercise"\n', encoding="utf-8"
    )

    record_path = tmp_path / "tasks" / "record.json"
    record_path.parent.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(popups, "HABIT_PATH", str(habits_path))
    monkeypatch.setattr(popups, "RECORD_PATH", str(record_path))

    # Mock ask_yes_no to return True for first habit, False for second
    call_count = [0]

    def mock_ask_yes_no(question, title):
        call_count[0] += 1
        return call_count[0] == 1  # True for first, False for second

    monkeypatch.setattr(popups, "ask_yes_no", mock_ask_yes_no)

    now = datetime(2025, 1, 2, 12, 0, 0)
    saved = popups.show_habit_tracking_popup(now=now)
    assert saved is True

    data = json.loads(record_path.read_text(encoding="utf-8"))
    assert isinstance(data, list)
    assert data[0]["date"] == "2025-01-02"
    assert data[0]["completed"] == {"1": "Get up early"}
    assert data[0]["timestamp"] == now.isoformat()

    # Reset and test with all habits skipped
    call_count[0] = 0

    def mock_ask_yes_no_all_false(question, title):
        return False

    monkeypatch.setattr(popups, "ask_yes_no", mock_ask_yes_no_all_false)
    saved_again = popups.show_habit_tracking_popup(now=now)
    assert saved_again is True

    data2 = json.loads(record_path.read_text(encoding="utf-8"))
    assert data2[0]["completed"] == {}


def test_show_habit_tracking_popup_cancel_does_not_save(tmp_path, monkeypatch):
    habits_path = tmp_path / "habits.toml"
    habits_path.write_text('[habits]\n1 = "Get up early"\n', encoding="utf-8")

    record_path = tmp_path / "tasks" / "record.json"
    record_path.parent.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(popups, "HABIT_PATH", str(habits_path))
    monkeypatch.setattr(popups, "RECORD_PATH", str(record_path))

    # Mock ask_yes_no to return None (user cancelled)
    monkeypatch.setattr(popups, "ask_yes_no", lambda question, title: None)

    saved = popups.show_habit_tracking_popup(now=datetime(2025, 1, 2, 12, 0, 0))
    assert saved is False
    assert (
        not record_path.exists()
        or record_path.read_text(encoding="utf-8").strip() == ""
    )
