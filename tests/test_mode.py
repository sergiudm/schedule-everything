import sys
from unittest.mock import patch, MagicMock
from pathlib import Path
from datetime import datetime, time, date

# Ensure src/ is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import schedule_management.reminder as reminder
from schedule_management.data.loaders import load_mode, save_mode
from schedule_management.commands.status import status_command, view_command
from schedule_management.commands.sync import sync_command
from schedule_management.runner import ScheduleRunner
from schedule_management.i18n import _t


class TestModePersistence:
    """Test saving and loading mode from mode.txt."""

    def test_default_mode_is_j(self, tmp_path, monkeypatch):
        # Point to a temporary file
        temp_mode_path = tmp_path / "tasks" / "mode.txt"
        monkeypatch.setattr("schedule_management.data.loaders.MODE_PATH", str(temp_mode_path))

        assert load_mode() == "j"

    def test_save_and_load_mode(self, tmp_path, monkeypatch):
        temp_mode_path = tmp_path / "tasks" / "mode.txt"
        monkeypatch.setattr("schedule_management.data.loaders.MODE_PATH", str(temp_mode_path))

        save_mode("p")
        assert load_mode() == "p"

        save_mode("j")
        assert load_mode() == "j"

    def test_invalid_mode_raises(self):
        try:
            save_mode("x")
            assert False, "Expected ValueError for invalid mode"
        except ValueError:
            pass


class TestModeCLI:
    """Test CLI commands under different modes."""

    @patch("schedule_management.commands.service._restart_reminder_service")
    def test_mode_command_display_and_switch(self, mock_restart, tmp_path, monkeypatch):
        temp_mode_path = tmp_path / "tasks" / "mode.txt"
        monkeypatch.setattr("schedule_management.commands.service.SETTINGS_PATH", str(tmp_path / "settings.toml"))
        monkeypatch.setattr("schedule_management.data.loaders.MODE_PATH", str(temp_mode_path))

        # 1. Check current mode when empty (default to j)
        args_view = MagicMock(mode=None)
        with patch("builtins.print") as mock_print:
            result = reminder.mode_command(args_view)
        assert result == 0
        mock_print.assert_called_once_with(_t("Current mode is {mode} mode").format(mode="j"))

        # 2. Switch to p mode
        mock_restart.return_value = (True, "")
        args_switch_p = MagicMock(mode="p")
        with patch("builtins.print") as mock_print:
            result = reminder.mode_command(args_switch_p)
        assert result == 0
        assert load_mode() == "p"
        mock_restart.assert_called_once()

        # 3. Switch back to j mode
        mock_restart.reset_mock()
        args_switch_j = MagicMock(mode="j")
        with patch("builtins.print") as mock_print:
            result = reminder.mode_command(args_switch_j)
        assert result == 0
        assert load_mode() == "j"
        mock_restart.assert_called_once()

    def test_disabled_commands_in_p_mode(self, tmp_path, monkeypatch):
        # Set mode to p
        temp_mode_path = tmp_path / "tasks" / "mode.txt"
        monkeypatch.setattr("schedule_management.data.loaders.MODE_PATH", str(temp_mode_path))
        save_mode("p")

        # Mock imports/functions used by commands to avoid other crashes
        monkeypatch.setattr("schedule_management.commands.status.load_mode", load_mode)
        monkeypatch.setattr("schedule_management.commands.sync.load_mode", load_mode)

        # Test rmd status
        args = MagicMock(verbose=False)
        with patch("builtins.print") as mock_print:
            status_result = status_command(args)
        assert status_result == 1
        mock_print.assert_any_call(_t("❌ Currently in p mode. Switch back to j mode to execute this command."))

        # Test rmd view
        with patch("builtins.print") as mock_print:
            view_result = view_command(args)
        assert view_result == 1
        mock_print.assert_any_call(_t("❌ Currently in p mode. Switch back to j mode to execute this command."))

        # Test rmd sync
        with patch("builtins.print") as mock_print:
            sync_result = sync_command(args)
        assert sync_result == 1
        mock_print.assert_any_call(_t("❌ Currently in p mode. Switch back to j mode to execute this command."))


class TestRunnerWithMode:
    """Test that ScheduleRunner respects p mode."""

    @patch("schedule_management.runner.alarm")
    def test_runner_skips_events_in_p_mode(self, mock_alarm, tmp_path, monkeypatch):
        # Set mode to p
        temp_mode_path = tmp_path / "tasks" / "mode.txt"
        monkeypatch.setattr("schedule_management.runner.load_mode", lambda: "p")

        # Configure runner dependencies
        config = MagicMock()
        config.should_skip_today.return_value = False
        config.time_blocks = {"pomodoro": 25}
        config.sound_file = "Ping"
        config.alarm_interval = 5
        config.max_alarm_duration = 300

        weekly = MagicMock()

        # Create runner
        runner = ScheduleRunner(config, weekly)

        # Trigger event directly under p mode
        runner._handle_event("09:00", "pomodoro")

        # Assert no alarm was triggered because p mode skips specific events!
        # Wait, runner._handle_event itself doesn't check the mode (the loop run() does).
        # So let's verify runner._handle_event triggers alarm, but run() skips it.
        # Yes, runner._handle_event will trigger alarms. Let's check run() logic:
        # We can mock today's schedule and test runner.run() in an iteration!

        # Let's test by subclassing runner or overriding the time.sleep to raise an exception
        # to break the infinite loop after one iteration.
        runner = ScheduleRunner(config, weekly)
        
        # Configure weekly schedule to return a valid event at 09:00
        weekly.get_today_schedule.return_value = {"09:00": "pomodoro"}
        
        # Mock datetime to be exactly 09:00
        mock_datetime = MagicMock()
        mock_datetime.now.return_value = datetime(2026, 5, 25, 9, 0, 0)
        monkeypatch.setattr("schedule_management.runner.datetime", mock_datetime)

        # Break the infinite loop by making time.sleep raise KeyboardInterrupt
        call_count = [0]
        def mock_sleep(seconds):
            call_count[0] += 1
            raise KeyboardInterrupt()

        monkeypatch.setattr("time.sleep", mock_sleep)

        # Run the runner (this will raise KeyboardInterrupt on first loop iteration)
        try:
            runner.run()
        except KeyboardInterrupt:
            pass

        # Since we are in p mode, specific events must be skipped!
        # Thus, runner._handle_event should NOT be called, and runner.notified_today should NOT contain "09:00"
        assert "09:00" not in runner.notified_today

        # -------------------------------------------------------------
        # Now let's test that in j mode, it DOES get notified/triggered!
        # -------------------------------------------------------------
        monkeypatch.setattr("schedule_management.runner.load_mode", lambda: "j")
        runner_j = ScheduleRunner(config, weekly)

        # Run the runner again in j mode
        try:
            runner_j.run()
        except KeyboardInterrupt:
            pass

        # It should trigger the event, so "09:00" will be added to notified_today
        assert "09:00" in runner_j.notified_today
