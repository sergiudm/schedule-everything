"""
Test suite for CLI commands in the reminder module.
Tests the update, view, and status commands using the new OOP architecture.
"""

import sys
import os
from unittest.mock import patch, MagicMock
from pathlib import Path
from datetime import datetime, time, date

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import schedule_management.reminder as reminder


class TestUpdateCommand:
    """Test the update command functionality."""

    @patch("schedule_management.reminder.subprocess.run")
    @patch("schedule_management.reminder.Path.exists")
    @patch("schedule_management.reminder.ScheduleConfig")
    @patch("schedule_management.reminder.WeeklySchedule")
    def test_update_success(
        self, mock_weekly, mock_config, mock_exists, mock_subprocess
    ):
        """Test successful update command."""
        mock_exists.return_value = True
        mock_subprocess.return_value = MagicMock(returncode=0, stderr="")

        args = MagicMock()
        result = reminder.update_command(args)

        assert result == 0
        assert mock_subprocess.call_count == 2  # unload + load

    @patch("schedule_management.reminder.ScheduleConfig")
    @patch("schedule_management.reminder.Path.exists")
    def test_update_invalid_config(self, mock_exists, mock_config):
        """Test update command with invalid configuration."""
        mock_exists.return_value = True
        mock_config.side_effect = Exception("Invalid config")

        args = MagicMock()
        result = reminder.update_command(args)

        assert result == 1

    @patch("schedule_management.reminder.Path.exists")
    def test_update_missing_files(self, mock_exists):
        """Test update command with missing configuration files."""
        mock_exists.return_value = False

        args = MagicMock()
        result = reminder.update_command(args)

        assert result == 1


class TestViewCommand:
    """Test the view command functionality."""

    @patch("schedule_management.reminder.ScheduleVisualizer")
    @patch("schedule_management.reminder.WeeklySchedule")
    @patch("schedule_management.reminder.ScheduleConfig")
    @patch("schedule_management.reminder.subprocess.run")
    def test_view_success(
        self, mock_subprocess, mock_config, mock_weekly, mock_visualizer
    ):
        """Test successful view command."""
        mock_visualizer_instance = MagicMock()
        mock_visualizer.return_value = mock_visualizer_instance
        mock_subprocess.return_value = MagicMock(returncode=0)

        args = MagicMock()
        result = reminder.view_command(args)

        assert result == 0
        mock_visualizer_instance.visualize.assert_called_once()

    @patch("schedule_management.reminder.ScheduleVisualizer")
    @patch("schedule_management.reminder.WeeklySchedule")
    @patch("schedule_management.reminder.ScheduleConfig")
    def test_view_visualization_error(self, mock_config, mock_weekly, mock_visualizer):
        """Test view command when visualization fails."""
        mock_visualizer.side_effect = Exception("Visualization error")

        args = MagicMock()
        result = reminder.view_command(args)

        assert result == 1


class TestStatusCommand:
    """Test the status command functionality."""

    @patch("schedule_management.reminder.get_today_schedule_for_status")
    @patch("schedule_management.reminder.get_week_parity")
    def test_status_normal_day(self, mock_week_parity, mock_get_schedule):
        """Test status command on a normal day."""
        mock_week_parity.return_value = "odd"
        mock_get_schedule.return_value = (
            {
                "09:00": "pomodoro",
                "10:00": {"block": "pomodoro", "title": "Focus Task"},
                "21:00": "summary",
            },
            "odd",
            False,
        )

        args = MagicMock(verbose=False)

        with patch("builtins.print") as mock_print:
            result = reminder.status_command(args)

            assert result == 0
            # Check that expected messages were printed (partial match)
            printed_lines = [call_args[0][0] for call_args in mock_print.call_args_list]
            assert "📊 Current week: odd" in printed_lines
            assert any(line.startswith("⏰ Next event:") for line in printed_lines)

    @patch("schedule_management.reminder.get_today_schedule_for_status")
    def test_status_skip_day(self, mock_get_schedule):
        """Test status command on a skipped day."""
        mock_get_schedule.return_value = ({}, "odd", True)

        args = MagicMock(verbose=False)

        with patch("builtins.print") as mock_print:
            result = reminder.status_command(args)

            assert result == 0
            mock_print.assert_any_call(
                "⏭️  Today is a skipped day - no reminders scheduled"
            )

    @patch("schedule_management.reminder.get_today_schedule_for_status")
    def test_status_no_schedule(self, mock_get_schedule):
        """Test status command when no schedule exists."""
        mock_get_schedule.return_value = ({}, "odd", False)

        args = MagicMock(verbose=False)

        with patch("builtins.print") as mock_print:
            result = reminder.status_command(args)

            assert result == 0
            mock_print.assert_any_call("📭 No more events scheduled for today")


class TestHelperFunctions:
    """Test helper functions used by the CLI commands."""

    def test_get_current_and_next_events_with_schedule(self):
        """Test get_current_and_next_events with a populated schedule."""
        test_schedule = {
            "08:00": "early_task",
            "10:00": {"block": "pomodoro", "title": "Focus Task"},
        }

        current, next_event, time_to_next = reminder.get_current_and_next_events(
            test_schedule
        )

        # Since we don't control the current time in this test,
        # we'll just verify the function doesn't crash and returns expected types
        assert isinstance(current, (str, type(None)))
        assert isinstance(next_event, (str, type(None)))
        assert isinstance(time_to_next, (str, type(None)))

    def test_get_current_and_next_events_empty_schedule(self):
        """Test get_current_and_next_events with empty schedule."""
        current, next_event, time_to_next = reminder.get_current_and_next_events({})

        assert current is None
        assert next_event is None
        assert time_to_next is None

    @patch("schedule_management.reminder.parse_time")
    @patch("schedule_management.reminder.datetime")
    def test_get_current_and_next_events_specific_times(
        self, mock_datetime, mock_parse_time
    ):
        """Test get_current_and_next_events with controlled time."""
        # Mock current time as 09:30
        mock_now = MagicMock()
        mock_now.time.return_value = time(9, 30)
        mock_now.strftime.return_value = "09:30"
        mock_now.date.return_value = date(2024, 1, 1)
        mock_datetime.now.return_value = mock_now
        mock_datetime.combine = datetime.combine

        # Mock parse_time to return specific times
        def mock_parse(time_str):
            if time_str == "08:00":
                return time(8, 0)
            elif time_str == "10:00":
                return time(10, 0)
            elif time_str == "14:00":
                return time(14, 0)
            return time(0, 0)

        mock_parse_time.side_effect = mock_parse

        test_schedule = {
            "08:00": "morning_task",
            "10:00": "focus_session",
            "14:00": "afternoon_meeting",
        }

        current, next_event, time_to_next = reminder.get_current_and_next_events(
            test_schedule
        )

        # Should have current event (08:00) and next event (10:00)
        assert current == "morning_task at 08:00"
        assert next_event == "focus_session at 10:00"
        assert time_to_next == "30m"

    @patch("schedule_management.reminder.ScheduleConfig")
    @patch("schedule_management.reminder.WeeklySchedule")
    def test_get_today_schedule_for_status_normal(self, mock_weekly, mock_config):
        """Test get_today_schedule_for_status on a normal day."""
        mock_config_instance = MagicMock()
        mock_config_instance.should_skip_today.return_value = False
        mock_config.return_value = mock_config_instance

        mock_weekly_instance = MagicMock()
        mock_weekly_instance.get_today_schedule.return_value = {"09:00": "pomodoro"}
        mock_weekly.return_value = mock_weekly_instance

        with patch("schedule_management.reminder.get_week_parity") as mock_parity:
            mock_parity.return_value = "odd"
            schedule, parity, is_skipped = reminder.get_today_schedule_for_status()

            assert schedule == {"09:00": "pomodoro"}
            assert parity == "odd"
            assert is_skipped is False

    @patch("schedule_management.reminder.ScheduleConfig")
    def test_get_today_schedule_for_status_skipped(self, mock_config):
        """Test get_today_schedule_for_status on a skipped day."""
        mock_config_instance = MagicMock()
        mock_config_instance.should_skip_today.return_value = True
        mock_config.return_value = mock_config_instance

        with patch("schedule_management.reminder.get_week_parity") as mock_parity:
            mock_parity.return_value = "even"
            schedule, parity, is_skipped = reminder.get_today_schedule_for_status()

            assert schedule == {}
            assert parity == "even"
            assert is_skipped is True


class TestMainFunction:
    """Test the main entry point function."""

    @patch("schedule_management.reminder.status_command")
    @patch("argparse.ArgumentParser.parse_args")
    def test_main_with_status_command(self, mock_parse_args, mock_status_command):
        """Test main function with status command."""
        mock_args = MagicMock()
        mock_args.command = "status"
        mock_args.func = mock_status_command
        mock_parse_args.return_value = mock_args
        mock_status_command.return_value = 0

        result = reminder.main()

        assert result == 0
        mock_status_command.assert_called_once_with(mock_args)

    @patch("argparse.ArgumentParser.print_help")
    @patch("argparse.ArgumentParser.parse_args")
    def test_main_no_command(self, mock_parse_args, mock_print_help):
        """Test main function with no command specified."""
        mock_args = MagicMock()
        mock_args.command = None
        mock_parse_args.return_value = mock_args

        result = reminder.main()

        assert result == 1
        mock_print_help.assert_called_once()

    @patch("schedule_management.reminder.update_command")
    @patch("argparse.ArgumentParser.parse_args")
    def test_main_keyboard_interrupt(self, mock_parse_args, mock_update_command):
        """Test main function handling keyboard interrupt."""
        mock_args = MagicMock()
        mock_args.command = "update"
        mock_args.func = mock_update_command
        mock_parse_args.return_value = mock_args
        mock_update_command.side_effect = KeyboardInterrupt()

        result = reminder.main()

        assert result == 1


class TestConfigPaths:
    """Test configuration path functions."""

    def test_get_config_paths(self):
        """Test the get_config_paths function."""
        paths = reminder.get_config_paths()

        assert "settings" in paths
        assert "odd_weeks" in paths
        assert "even_weeks" in paths

        for path in paths.values():
            assert isinstance(path, Path)
            assert "config" in str(path)
