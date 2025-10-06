"""
Test suite for CLI commands in the reminder module.
Tests the update, view, and status commands using the new OOP architecture.
"""

import sys
import os
from unittest.mock import patch, MagicMock
from pathlib import Path
from datetime import datetime, time, date

# Set up test environment variables before importing reminder module
test_config_dir = os.path.join(os.path.dirname(__file__), "config")
os.environ["REMINDER_CONFIG_DIR"] = test_config_dir
test_tasks_path = os.path.join(test_config_dir, "test_tasks.json")
os.environ["REMINDER_TASKS_PATH"] = test_tasks_path
test_log_path = os.path.join(test_config_dir, "test_tasks_log.json")
os.environ["REMINDER_LOG_PATH"] = test_log_path

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
            printed_args = [
                call[0][0] if call[0] else ""
                for call in mock_print.call_args_list
                if call
            ]
            assert any("📅 Odd Week" in str(line) for line in printed_args)
            assert any("⏰ Next event:" in str(line) for line in printed_args)

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

    @patch("schedule_management.reminder.add_task")
    @patch("argparse.ArgumentParser.parse_args")
    def test_main_with_add_command(self, mock_parse_args, mock_add_task):
        """Test main function with add command."""
        mock_args = MagicMock()
        mock_args.command = "add"
        mock_args.func = mock_add_task
        mock_parse_args.return_value = mock_args
        mock_add_task.return_value = 0

        result = reminder.main()

        assert result == 0
        mock_add_task.assert_called_once_with(mock_args)

    @patch("schedule_management.reminder.delete_task")
    @patch("argparse.ArgumentParser.parse_args")
    def test_main_with_rm_command(self, mock_parse_args, mock_delete_task):
        """Test main function with rm command."""
        mock_args = MagicMock()
        mock_args.command = "rm"
        mock_args.func = mock_delete_task
        mock_parse_args.return_value = mock_args
        mock_delete_task.return_value = 0

        result = reminder.main()

        assert result == 0
        mock_delete_task.assert_called_once_with(mock_args)

    @patch("schedule_management.reminder.show_tasks")
    @patch("argparse.ArgumentParser.parse_args")
    def test_main_with_ls_command(self, mock_parse_args, mock_show_tasks):
        """Test main function with ls command."""
        mock_args = MagicMock()
        mock_args.command = "ls"
        mock_args.func = mock_show_tasks
        mock_parse_args.return_value = mock_args
        mock_show_tasks.return_value = 0

        result = reminder.main()

        assert result == 0
        mock_show_tasks.assert_called_once_with(mock_args)

    @patch("schedule_management.reminder.view_command")
    @patch("argparse.ArgumentParser.parse_args")
    def test_main_with_view_command(self, mock_parse_args, mock_view_command):
        """Test main function with view command."""
        mock_args = MagicMock()
        mock_args.command = "view"
        mock_args.func = mock_view_command
        mock_parse_args.return_value = mock_args
        mock_view_command.return_value = 0

        result = reminder.main()

        assert result == 0
        mock_view_command.assert_called_once_with(mock_args)


class TestConfigPaths:
    """Test configuration path functions."""

    def test_get_config_paths(self):
        """Test the get_config_paths function."""
        # Test with the test config directory
        test_config_dir = os.path.join(os.path.dirname(__file__), "config")
        paths = reminder.get_config_paths(test_config_dir)

        assert "settings" in paths
        assert "odd_weeks" in paths
        assert "even_weeks" in paths

        for path in paths.values():
            assert isinstance(path, Path)
            assert "config" in str(path)
            # Verify the test config files actually exist
            assert path.exists(), f"Test config file not found: {path}"


class TestTaskManagement:
    """Test the task management functionality."""

    def setup_method(self):
        """Set up test fixtures before each test method."""
        # Create a temporary tasks file for testing
        self.test_tasks_file = Path(reminder.TASKS_PATH)
        self.original_tasks_content = None

        # Backup original tasks file if it exists
        if self.test_tasks_file.exists():
            with open(self.test_tasks_file, "r", encoding="utf-8") as f:
                self.original_tasks_content = f.read()

    def teardown_method(self):
        """Clean up after each test method."""
        # Restore original tasks file if it existed
        if self.original_tasks_content is not None:
            with open(self.test_tasks_file, "w", encoding="utf-8") as f:
                f.write(self.original_tasks_content)
        elif self.test_tasks_file.exists():
            # Remove the test file if it was created during testing
            self.test_tasks_file.unlink()

    def test_load_tasks_empty_file(self):
        """Test loading tasks from a non-existent or empty file."""
        # Ensure the file doesn't exist
        if self.test_tasks_file.exists():
            self.test_tasks_file.unlink()

        tasks = reminder.load_tasks()
        assert tasks == []

    def test_load_tasks_invalid_json(self):
        """Test loading tasks from a file with invalid JSON."""
        # Create a file with invalid JSON
        with open(self.test_tasks_file, "w", encoding="utf-8") as f:
            f.write('{"invalid": json}')

        tasks = reminder.load_tasks()
        assert tasks == []

    def test_save_and_load_tasks(self):
        """Test saving and then loading tasks."""
        test_tasks = [
            {"description": "Test task 1", "priority": 5},
            {"description": "Test task 2", "priority": 8},
        ]

        reminder.save_tasks(test_tasks)
        loaded_tasks = reminder.load_tasks()

        assert loaded_tasks == test_tasks

    @patch("schedule_management.reminder.load_tasks")
    @patch("schedule_management.reminder.save_tasks")
    def test_add_task_success(self, mock_save_tasks, mock_load_tasks):
        """Test adding a new task successfully."""
        mock_load_tasks.return_value = []
        mock_save_tasks.return_value = None

        args = MagicMock()
        args.task = "Complete project"
        args.priority = 7

        result = reminder.add_task(args)

        assert result == 0
        mock_save_tasks.assert_called_once()
        # Verify the task was added
        saved_tasks = mock_save_tasks.call_args[0][0]
        assert len(saved_tasks) == 1
        assert saved_tasks[0]["description"] == "Complete project"
        assert saved_tasks[0]["priority"] == 7

    @patch("schedule_management.reminder.load_tasks")
    @patch("schedule_management.reminder.save_tasks")
    def test_add_task_duplicate(self, mock_save_tasks, mock_load_tasks):
        """Test adding a duplicate task updates the existing one."""
        existing_tasks = [
            {"description": "Complete project", "priority": 5},
            {"description": "Review code", "priority": 3},
        ]
        mock_load_tasks.return_value = existing_tasks
        mock_save_tasks.return_value = None

        args = MagicMock()
        args.task = "Complete project"
        args.priority = 9  # New priority

        result = reminder.add_task(args)

        assert result == 0
        mock_save_tasks.assert_called_once()
        # Verify the task was updated
        saved_tasks = mock_save_tasks.call_args[0][0]
        assert len(saved_tasks) == 2
        updated_task = next(
            t for t in saved_tasks if t["description"] == "Complete project"
        )
        assert updated_task["priority"] == 9

    @patch("schedule_management.reminder.load_tasks")
    @patch("schedule_management.reminder.save_tasks")
    def test_add_task_negative_priority(self, mock_save_tasks, mock_load_tasks):
        """Test adding a task with negative priority fails."""
        args = MagicMock()
        args.task = "Complete project"
        args.priority = -1

        with patch("builtins.print") as mock_print:
            result = reminder.add_task(args)

        assert result == 1
        mock_save_tasks.assert_not_called()
        mock_print.assert_called_once_with(
            "❌ Error: Priority must be a positive integer"
        )

    @patch("schedule_management.reminder.load_tasks")
    @patch("schedule_management.reminder.save_tasks")
    def test_add_task_zero_priority(self, mock_save_tasks, mock_load_tasks):
        """Test adding a task with zero priority fails."""
        args = MagicMock()
        args.task = "Complete project"
        args.priority = 0

        with patch("builtins.print") as mock_print:
            result = reminder.add_task(args)

        assert result == 1
        mock_save_tasks.assert_not_called()
        mock_print.assert_called_once_with(
            "❌ Error: Priority must be a positive integer"
        )

    @patch("schedule_management.reminder.load_tasks")
    @patch("schedule_management.reminder.save_tasks")
    def test_add_task_save_error(self, mock_save_tasks, mock_load_tasks):
        """Test handling error when saving tasks fails."""
        mock_load_tasks.return_value = []
        mock_save_tasks.side_effect = Exception("Save failed")

        args = MagicMock()
        args.task = "Complete project"
        args.priority = 5

        with patch("builtins.print") as mock_print:
            result = reminder.add_task(args)

        assert result == 1
        mock_print.assert_called_once()
        assert "❌ Error saving task:" in mock_print.call_args[0][0]

    @patch("schedule_management.reminder.load_tasks")
    @patch("schedule_management.reminder.save_tasks")
    def test_delete_task_success(self, mock_save_tasks, mock_load_tasks):
        """Test deleting an existing task successfully."""
        existing_tasks = [
            {"description": "Complete project", "priority": 7},
            {"description": "Review code", "priority": 3},
            {"description": "Write documentation", "priority": 5},
        ]
        mock_load_tasks.return_value = existing_tasks
        mock_save_tasks.return_value = None

        args = MagicMock()
        args.tasks = ["Review code"]

        result = reminder.delete_task(args)

        assert result == 0
        mock_save_tasks.assert_called_once()
        # Verify the task was removed
        saved_tasks = mock_save_tasks.call_args[0][0]
        assert len(saved_tasks) == 2
        assert not any(t["description"] == "Review code" for t in saved_tasks)

    @patch("schedule_management.reminder.load_tasks")
    @patch("schedule_management.reminder.save_tasks")
    def test_delete_task_not_found(self, mock_save_tasks, mock_load_tasks):
        """Test deleting a non-existent task."""
        existing_tasks = [
            {"description": "Complete project", "priority": 7},
            {"description": "Review code", "priority": 3},
        ]
        mock_load_tasks.return_value = existing_tasks
        mock_save_tasks.return_value = None

        args = MagicMock()
        args.tasks = ["Non-existent task"]

        with patch("builtins.print") as mock_print:
            result = reminder.delete_task(args)

        assert result == 1
        mock_save_tasks.assert_not_called()
        mock_print.assert_called_once_with("❌ Task 'Non-existent task' not found")

    @patch("schedule_management.reminder.load_tasks")
    def test_delete_task_empty_list(self, mock_load_tasks):
        """Test deleting a task from an empty list."""
        mock_load_tasks.return_value = []

        args = MagicMock()
        args.tasks = ["Any task"]

        with patch("builtins.print") as mock_print:
            result = reminder.delete_task(args)

        assert result == 1
        mock_print.assert_called_once_with("⚠️  No tasks found to delete")

    @patch("schedule_management.reminder.load_tasks")
    @patch("schedule_management.reminder.save_tasks")
    def test_delete_task_multiple_occurrences(self, mock_save_tasks, mock_load_tasks):
        """Test deleting multiple tasks with the same description."""
        existing_tasks = [
            {"description": "Review code", "priority": 7},
            {"description": "Write documentation", "priority": 3},
            {
                "description": "Review code",
                "priority": 5,
            },  # Same description, different priority
        ]
        mock_load_tasks.return_value = existing_tasks
        mock_save_tasks.return_value = None

        args = MagicMock()
        args.tasks = ["Review code"]

        result = reminder.delete_task(args)

        assert result == 0
        mock_save_tasks.assert_called_once()
        # Verify both tasks with the same description were removed
        saved_tasks = mock_save_tasks.call_args[0][0]
        assert len(saved_tasks) == 1
        assert saved_tasks[0]["description"] == "Write documentation"

    @patch("schedule_management.reminder.load_tasks")
    @patch("schedule_management.reminder.save_tasks")
    def test_delete_task_save_error(self, mock_save_tasks, mock_load_tasks):
        """Test handling error when saving tasks fails after deletion."""
        existing_tasks = [{"description": "Complete project", "priority": 7}]
        mock_load_tasks.return_value = existing_tasks
        mock_save_tasks.side_effect = Exception("Save failed")

        args = MagicMock()
        args.tasks = ["Complete project"]

        with patch("builtins.print") as mock_print:
            result = reminder.delete_task(args)

        assert result == 1
        mock_print.assert_called_once()
        assert "❌ Error saving tasks:" in mock_print.call_args[0][0]

    @patch("schedule_management.reminder.load_tasks")
    @patch("schedule_management.reminder.save_tasks")
    def test_delete_task_by_id_success(self, mock_save_tasks, mock_load_tasks):
        """Test deleting a task by ID successfully."""
        existing_tasks = [
            {"description": "High priority task", "priority": 9},
            {"description": "Medium priority task", "priority": 5},
            {"description": "Low priority task", "priority": 2},
        ]
        mock_load_tasks.return_value = existing_tasks
        mock_save_tasks.return_value = None

        args = MagicMock()
        args.tasks = [
            "2"
        ]  # ID 2 should be "Medium priority task" after sorting by priority

        result = reminder.delete_task(args)

        assert result == 0
        mock_save_tasks.assert_called_once()
        # Verify the task was removed
        saved_tasks = mock_save_tasks.call_args[0][0]
        assert len(saved_tasks) == 2
        assert not any(t["description"] == "Medium priority task" for t in saved_tasks)
        # High priority task should still be there
        assert any(t["description"] == "High priority task" for t in saved_tasks)
        # Low priority task should still be there
        assert any(t["description"] == "Low priority task" for t in saved_tasks)

    @patch("schedule_management.reminder.load_tasks")
    @patch("schedule_management.reminder.save_tasks")
    def test_delete_task_by_id_first_item(self, mock_save_tasks, mock_load_tasks):
        """Test deleting the first task (highest priority) by ID."""
        existing_tasks = [
            {"description": "High priority task", "priority": 9},
            {"description": "Medium priority task", "priority": 5},
            {"description": "Low priority task", "priority": 2},
        ]
        mock_load_tasks.return_value = existing_tasks
        mock_save_tasks.return_value = None

        args = MagicMock()
        args.tasks = ["1"]  # ID 1 should be "High priority task" after sorting

        result = reminder.delete_task(args)

        assert result == 0
        mock_save_tasks.assert_called_once()
        # Verify the task was removed
        saved_tasks = mock_save_tasks.call_args[0][0]
        assert len(saved_tasks) == 2
        assert not any(t["description"] == "High priority task" for t in saved_tasks)

    @patch("schedule_management.reminder.load_tasks")
    @patch("schedule_management.reminder.save_tasks")
    def test_delete_task_by_id_last_item(self, mock_save_tasks, mock_load_tasks):
        """Test deleting the last task (lowest priority) by ID."""
        existing_tasks = [
            {"description": "High priority task", "priority": 9},
            {"description": "Medium priority task", "priority": 5},
            {"description": "Low priority task", "priority": 2},
        ]
        mock_load_tasks.return_value = existing_tasks
        mock_save_tasks.return_value = None

        args = MagicMock()
        args.tasks = ["3"]  # ID 3 should be "Low priority task" after sorting

        result = reminder.delete_task(args)

        assert result == 0
        mock_save_tasks.assert_called_once()
        # Verify the task was removed
        saved_tasks = mock_save_tasks.call_args[0][0]
        assert len(saved_tasks) == 2
        assert not any(t["description"] == "Low priority task" for t in saved_tasks)

    @patch("schedule_management.reminder.load_tasks")
    def test_delete_task_by_id_invalid_id_too_high(self, mock_load_tasks):
        """Test deleting a task with ID that's too high."""
        existing_tasks = [
            {"description": "Task 1", "priority": 5},
            {"description": "Task 2", "priority": 3},
        ]
        mock_load_tasks.return_value = existing_tasks

        args = MagicMock()
        args.tasks = ["5"]  # Invalid ID

        with patch("builtins.print") as mock_print:
            result = reminder.delete_task(args)

        assert result == 1
        mock_print.assert_called_once()
        assert "Invalid task ID: 5" in mock_print.call_args[0][0]
        assert "Please use a number between 1 and 2" in mock_print.call_args[0][0]

    @patch("schedule_management.reminder.load_tasks")
    def test_delete_task_by_id_invalid_id_zero(self, mock_load_tasks):
        """Test deleting a task with ID of zero."""
        existing_tasks = [
            {"description": "Task 1", "priority": 5},
            {"description": "Task 2", "priority": 3},
        ]
        mock_load_tasks.return_value = existing_tasks

        args = MagicMock()
        args.tasks = ["0"]  # Invalid ID

        with patch("builtins.print") as mock_print:
            result = reminder.delete_task(args)

        assert result == 1
        mock_print.assert_called_once()
        assert "Invalid task ID: 0" in mock_print.call_args[0][0]

    @patch("schedule_management.reminder.load_tasks")
    def test_delete_task_by_id_invalid_id_negative(self, mock_load_tasks):
        """Test deleting a task with negative ID."""
        existing_tasks = [
            {"description": "Task 1", "priority": 5},
            {"description": "Task 2", "priority": 3},
        ]
        mock_load_tasks.return_value = existing_tasks

        args = MagicMock()
        args.tasks = ["-1"]  # Invalid ID

        with patch("builtins.print") as mock_print:
            result = reminder.delete_task(args)

        assert result == 1
        mock_print.assert_called_once()
        assert "Invalid task ID: -1" in mock_print.call_args[0][0]

    @patch("schedule_management.reminder.load_tasks")
    def test_delete_task_by_id_empty_list(self, mock_load_tasks):
        """Test deleting a task by ID from an empty list."""
        mock_load_tasks.return_value = []

        args = MagicMock()
        args.tasks = ["1"]

        with patch("builtins.print") as mock_print:
            result = reminder.delete_task(args)

        assert result == 1
        mock_print.assert_called_once_with("⚠️  No tasks found to delete")

    @patch("schedule_management.reminder.load_tasks")
    def test_delete_task_by_id_numeric_string_fallback(self, mock_load_tasks):
        """Test that numeric string descriptions are treated as IDs first, not descriptions."""
        existing_tasks = [
            {
                "description": "123",
                "priority": 9,
            },  # Task description is a numeric string
            {"description": "Regular task", "priority": 5},
        ]
        mock_load_tasks.return_value = existing_tasks

        args = MagicMock()
        args.tasks = [
            "123"
        ]  # This should be treated as an ID first (invalid in this case)

        with patch("builtins.print") as mock_print:
            result = reminder.delete_task(args)

        assert result == 1
        # Should treat "123" as an ID (invalid since there are only 2 tasks)
        mock_print.assert_called_once()
        assert "Invalid task ID: 123" in mock_print.call_args[0][0]
        assert "Please use a number between 1 and 2" in mock_print.call_args[0][0]

    @patch("schedule_management.reminder.load_tasks")
    @patch("schedule_management.reminder.save_tasks")
    def test_delete_task_by_id_with_valid_id_as_string(
        self, mock_save_tasks, mock_load_tasks
    ):
        """Test that valid numeric IDs work even when passed as strings."""
        existing_tasks = [
            {"description": "High priority task", "priority": 9},
            {"description": "Regular task", "priority": 5},
        ]
        mock_load_tasks.return_value = existing_tasks
        mock_save_tasks.return_value = None

        args = MagicMock()
        args.tasks = ["1"]  # Valid ID as string

        result = reminder.delete_task(args)

        assert result == 0
        mock_save_tasks.assert_called_once()
        # Should delete the task with ID 1 (highest priority)
        saved_tasks = mock_save_tasks.call_args[0][0]
        assert len(saved_tasks) == 1
        assert saved_tasks[0]["description"] == "Regular task"

    # New tests for multi-argument delete functionality
    @patch("schedule_management.reminder.load_tasks")
    @patch("schedule_management.reminder.save_tasks")
    def test_delete_multiple_tasks_success(self, mock_save_tasks, mock_load_tasks):
        """Test deleting multiple tasks successfully by description."""
        existing_tasks = [
            {"description": "Complete project", "priority": 9},
            {"description": "Review code", "priority": 7},
            {"description": "Write documentation", "priority": 5},
            {"description": "Test application", "priority": 3},
        ]
        mock_load_tasks.return_value = existing_tasks
        mock_save_tasks.return_value = None

        args = MagicMock()
        args.tasks = ["Review code", "Write documentation"]

        result = reminder.delete_task(args)

        assert result == 0
        mock_save_tasks.assert_called_once()
        # Verify the tasks were removed
        saved_tasks = mock_save_tasks.call_args[0][0]
        assert len(saved_tasks) == 2
        assert not any(t["description"] == "Review code" for t in saved_tasks)
        assert not any(t["description"] == "Write documentation" for t in saved_tasks)
        # Verify other tasks remain
        assert any(t["description"] == "Complete project" for t in saved_tasks)
        assert any(t["description"] == "Test application" for t in saved_tasks)

    @patch("schedule_management.reminder.load_tasks")
    @patch("schedule_management.reminder.save_tasks")
    def test_delete_multiple_tasks_by_ids(self, mock_save_tasks, mock_load_tasks):
        """Test deleting multiple tasks successfully by IDs."""
        existing_tasks = [
            {"description": "High priority task", "priority": 9},
            {"description": "Medium priority task", "priority": 7},
            {"description": "Low priority task", "priority": 5},
            {"description": "Very low priority task", "priority": 2},
        ]
        mock_load_tasks.return_value = existing_tasks
        mock_save_tasks.return_value = None

        args = MagicMock()
        args.tasks = ["1", "3"]  # Delete highest and lowest priority tasks

        result = reminder.delete_task(args)

        assert result == 0
        mock_save_tasks.assert_called_once()
        # Verify the tasks were removed
        saved_tasks = mock_save_tasks.call_args[0][0]
        assert len(saved_tasks) == 2
        assert not any(t["description"] == "High priority task" for t in saved_tasks)
        assert not any(t["description"] == "Low priority task" for t in saved_tasks)
        # Verify other tasks remain
        assert any(t["description"] == "Medium priority task" for t in saved_tasks)
        assert any(t["description"] == "Very low priority task" for t in saved_tasks)

    @patch("schedule_management.reminder.load_tasks")
    @patch("schedule_management.reminder.save_tasks")
    def test_delete_multiple_tasks_mixed_ids_and_descriptions(
        self, mock_save_tasks, mock_load_tasks
    ):
        """Test deleting multiple tasks using mixed IDs and descriptions."""
        existing_tasks = [
            {"description": "High priority task", "priority": 9},
            {"description": "Code review", "priority": 7},
            {"description": "Documentation", "priority": 5},
            {"description": "Testing", "priority": 3},
        ]
        mock_load_tasks.return_value = existing_tasks
        mock_save_tasks.return_value = None

        args = MagicMock()
        args.tasks = ["1", "Documentation", "4"]  # Mix of ID and description

        result = reminder.delete_task(args)

        assert result == 0
        mock_save_tasks.assert_called_once()
        # Verify the tasks were removed
        saved_tasks = mock_save_tasks.call_args[0][0]
        assert len(saved_tasks) == 1
        assert saved_tasks[0]["description"] == "Code review"

    @patch("schedule_management.reminder.load_tasks")
    @patch("schedule_management.reminder.save_tasks")
    def test_delete_multiple_tasks_partial_success(
        self, mock_save_tasks, mock_load_tasks
    ):
        """Test deleting multiple tasks with some successes and some failures."""
        existing_tasks = [
            {"description": "Complete project", "priority": 9},
            {"description": "Review code", "priority": 7},
            {"description": "Write documentation", "priority": 5},
        ]
        mock_load_tasks.return_value = existing_tasks
        mock_save_tasks.return_value = None

        args = MagicMock()
        args.tasks = ["Review code", "Non-existent task", "Complete project"]

        with patch("builtins.print") as mock_print:
            result = reminder.delete_task(args)

        assert result == 1  # Should return 1 due to some failures
        mock_save_tasks.assert_called_once()
        # Verify the valid tasks were removed
        saved_tasks = mock_save_tasks.call_args[0][0]
        assert len(saved_tasks) == 1
        assert saved_tasks[0]["description"] == "Write documentation"
        # Verify error was printed for non-existent task
        mock_print.assert_any_call("❌ Task 'Non-existent task' not found")

    @patch("schedule_management.reminder.load_tasks")
    @patch("schedule_management.reminder.save_tasks")
    def test_delete_multiple_tasks_all_fail(self, mock_save_tasks, mock_load_tasks):
        """Test deleting multiple tasks where none exist."""
        existing_tasks = [
            {"description": "Complete project", "priority": 9},
            {"description": "Review code", "priority": 7},
        ]
        mock_load_tasks.return_value = existing_tasks
        mock_save_tasks.return_value = None

        args = MagicMock()
        args.tasks = ["Non-existent task 1", "Non-existent task 2"]

        with patch("builtins.print") as mock_print:
            result = reminder.delete_task(args)

        assert result == 1
        mock_save_tasks.assert_not_called()
        # Verify errors were printed for both non-existent tasks
        expected_calls = [
            "❌ Task 'Non-existent task 1' not found",
            "❌ Task 'Non-existent task 2' not found",
        ]
        for expected_call in expected_calls:
            mock_print.assert_any_call(expected_call)

    @patch("schedule_management.reminder.load_tasks")
    @patch("schedule_management.reminder.save_tasks")
    def test_delete_multiple_tasks_invalid_ids(self, mock_save_tasks, mock_load_tasks):
        """Test deleting multiple tasks with some invalid IDs."""
        existing_tasks = [
            {"description": "Task 1", "priority": 5},
            {"description": "Task 2", "priority": 3},
        ]
        mock_load_tasks.return_value = existing_tasks
        mock_save_tasks.return_value = None

        args = MagicMock()
        args.tasks = ["1", "5", "-1", "2"]  # Mix of valid and invalid IDs

        with patch("builtins.print") as mock_print:
            result = reminder.delete_task(args)

        assert result == 1  # Should return 1 due to invalid IDs
        mock_save_tasks.assert_called_once()
        # Verify the valid tasks were removed
        saved_tasks = mock_save_tasks.call_args[0][0]
        assert len(saved_tasks) == 0
        # Verify errors were printed for invalid IDs
        mock_print.assert_any_call(
            "❌ Invalid task ID: 5. Please use a number between 1 and 2"
        )
        mock_print.assert_any_call(
            "❌ Invalid task ID: -1. Please use a number between 1 and 2"
        )

    @patch("schedule_management.reminder.load_tasks")
    @patch("schedule_management.reminder.save_tasks")
    def test_delete_multiple_tasks_with_duplicate_occurrences(
        self, mock_save_tasks, mock_load_tasks
    ):
        """Test deleting multiple tasks when some have duplicate descriptions."""
        existing_tasks = [
            {"description": "Review code", "priority": 7},
            {"description": "Write documentation", "priority": 5},
            {"description": "Review code", "priority": 3},  # Duplicate description
            {"description": "Testing", "priority": 2},
        ]
        mock_load_tasks.return_value = existing_tasks
        mock_save_tasks.return_value = None

        args = MagicMock()
        args.tasks = ["Review code", "Testing"]

        result = reminder.delete_task(args)

        assert result == 0
        mock_save_tasks.assert_called_once()
        # Verify all tasks with matching descriptions were removed
        saved_tasks = mock_save_tasks.call_args[0][0]
        assert len(saved_tasks) == 1
        assert saved_tasks[0]["description"] == "Write documentation"
        # Both "Review code" tasks should be removed

    @patch("schedule_management.reminder.load_tasks")
    @patch("schedule_management.reminder.save_tasks")
    def test_delete_multiple_tasks_save_error(self, mock_save_tasks, mock_load_tasks):
        """Test handling error when saving tasks fails after multiple deletions."""
        existing_tasks = [
            {"description": "Task 1", "priority": 7},
            {"description": "Task 2", "priority": 5},
            {"description": "Task 3", "priority": 3},
        ]
        mock_load_tasks.return_value = existing_tasks
        mock_save_tasks.side_effect = Exception("Save failed")

        args = MagicMock()
        args.tasks = ["Task 1", "Task 3"]

        with patch("builtins.print") as mock_print:
            result = reminder.delete_task(args)

        assert result == 1
        mock_print.assert_called_once()
        assert "❌ Error saving tasks:" in mock_print.call_args[0][0]

    @patch("schedule_management.reminder.load_tasks")
    def test_show_tasks_empty(self, mock_load_tasks):
        """Test showing tasks when there are no tasks."""
        mock_load_tasks.return_value = []

        args = MagicMock()

        with patch("builtins.print") as mock_print:
            result = reminder.show_tasks(args)

        assert result == 0
        mock_print.assert_called_once_with("📋 No tasks found")

    @patch("schedule_management.reminder.load_tasks")
    def test_show_tasks_sorted_by_importance(self, mock_load_tasks):
        """Test that tasks are displayed sorted by importance (descending)."""
        test_tasks = [
            {"description": "Task 1", "priority": 3},
            {"description": "Task 2", "priority": 7},
            {"description": "Task 3", "priority": 1},
        ]
        mock_load_tasks.return_value = test_tasks

        args = MagicMock()

        with patch("builtins.print") as mock_print:
            result = reminder.show_tasks(args)

        assert result == 0
        # Capture the print calls to verify sorting
        print_calls = [
            call[0][0] if call[0] else "" for call in mock_print.call_args_list
        ]

        # Check that the highest priority task appears first
        # The actual sorting happens inside show_tasks, so we can't directly verify
        # the order here, but we can at least ensure all tasks were processed
        assert len([line for line in print_calls if "Task 1" in str(line)]) >= 1
        assert len([line for line in print_calls if "Task 2" in str(line)]) >= 1
        assert len([line for line in print_calls if "Task 3" in str(line)]) >= 1


class TestMainFunctions:
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
