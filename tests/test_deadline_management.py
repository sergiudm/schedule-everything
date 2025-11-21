"""
Test suite for deadline management commands.
Tests the add_deadline, delete_deadline, and show_deadlines commands.
"""

import sys
import json
from unittest.mock import patch, MagicMock, mock_open
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
import schedule_management.reminder as reminder

# Define the test config directory to use throughout the tests
TEST_CONFIG_DIR = Path(__file__).resolve().parent / "config"


class TestDeadlineHelperFunctions:
    """Test helper functions for deadline management."""

    @patch("schedule_management.reminder.Path.exists")
    @patch("builtins.open", new_callable=mock_open, read_data="[]")
    def test_load_deadlines_empty(self, mock_file, mock_exists):
        """Test loading deadlines from empty file."""
        mock_exists.return_value = True

        with patch("schedule_management.reminder.get_ddl_path") as mock_path:
            mock_path.return_value = Path("/test/ddl.json")
            deadlines = reminder.load_deadlines()

        assert deadlines == []

    @patch("schedule_management.reminder.Path.exists")
    def test_load_deadlines_not_found(self, mock_exists):
        """Test loading deadlines when file doesn't exist."""
        mock_exists.return_value = False

        with patch("schedule_management.reminder.get_ddl_path") as mock_path:
            mock_path.return_value = Path("/test/ddl.json")
            deadlines = reminder.load_deadlines()

        assert deadlines == []

    @patch("schedule_management.reminder.Path.exists")
    @patch("builtins.open", new_callable=mock_open, read_data='{"invalid": json}')
    def test_load_deadlines_invalid_json(self, mock_file, mock_exists):
        """Test loading deadlines with invalid JSON."""
        mock_exists.return_value = True

        with patch("schedule_management.reminder.get_ddl_path") as mock_path:
            mock_path.return_value = Path("/test/ddl.json")
            deadlines = reminder.load_deadlines()

        assert deadlines == []

    @patch("schedule_management.reminder.Path.exists")
    @patch("builtins.open", new_callable=mock_open)
    def test_load_deadlines_success(self, mock_file, mock_exists):
        """Test loading valid deadlines."""
        test_data = [
            {
                "event": "homework2",
                "deadline": "2026-07-04",
                "added": "2025-11-22T10:00:00Z",
            },
            {
                "event": "project",
                "deadline": "2025-12-25",
                "added": "2025-11-22T11:00:00Z",
            },
        ]
        mock_file.return_value.read.return_value = json.dumps(test_data)
        mock_exists.return_value = True

        with patch("schedule_management.reminder.get_ddl_path") as mock_path:
            mock_path.return_value = Path("/test/ddl.json")
            with patch("json.load", return_value=test_data):
                deadlines = reminder.load_deadlines()

        assert len(deadlines) == 2
        assert deadlines[0]["event"] == "homework2"

    @patch("schedule_management.reminder.Path.mkdir")
    @patch("builtins.open", new_callable=mock_open)
    def test_save_deadlines(self, mock_file, mock_mkdir):
        """Test saving deadlines to file."""
        test_deadlines = [
            {
                "event": "homework2",
                "deadline": "2026-07-04",
                "added": "2025-11-22T10:00:00Z",
            }
        ]

        with patch("schedule_management.reminder.get_ddl_path") as mock_path:
            mock_path.return_value = Path("/test/ddl.json")
            reminder.save_deadlines(test_deadlines)

        mock_mkdir.assert_called_once()
        mock_file.assert_called_once()


class TestAddDeadline:
    """Test the add_deadline command functionality."""

    @patch("schedule_management.reminder.save_deadlines")
    @patch("schedule_management.reminder.load_deadlines")
    @patch("schedule_management.reminder.datetime")
    def test_add_deadline_success(self, mock_datetime, mock_load, mock_save):
        """Test adding a new deadline successfully."""
        # Mock current date as November 22, 2025
        mock_now = MagicMock()
        mock_now.date.return_value = datetime(2025, 11, 22).date()
        mock_now.year = 2025
        mock_datetime.now.return_value = mock_now
        mock_datetime.side_effect = lambda *args, **kw: datetime(*args, **kw)

        mock_load.return_value = []

        args = MagicMock()
        args.event = "homework2"
        args.date = "7.4"  # July 4th

        with patch("builtins.print") as mock_print:
            result = reminder.add_deadline(args)

        assert result == 0
        mock_save.assert_called_once()
        saved_deadlines = mock_save.call_args[0][0]
        assert len(saved_deadlines) == 1
        assert saved_deadlines[0]["event"] == "homework2"
        assert (
            "2026-07-04" in saved_deadlines[0]["deadline"]
        )  # Next year since July passed
        mock_print.assert_called_once()
        assert "✅" in mock_print.call_args[0][0]

    @patch("schedule_management.reminder.save_deadlines")
    @patch("schedule_management.reminder.load_deadlines")
    @patch("schedule_management.reminder.datetime")
    def test_add_deadline_current_year(self, mock_datetime, mock_load, mock_save):
        """Test adding a deadline for date that hasn't passed this year."""
        # Mock current date as November 22, 2025
        mock_now = MagicMock()
        mock_now.date.return_value = datetime(2025, 11, 22).date()
        mock_now.year = 2025
        mock_datetime.now.return_value = mock_now
        mock_datetime.side_effect = lambda *args, **kw: datetime(*args, **kw)

        mock_load.return_value = []

        args = MagicMock()
        args.event = "exam"
        args.date = "12.15"  # December 15th - hasn't passed yet

        with patch("builtins.print"):
            result = reminder.add_deadline(args)

        assert result == 0
        saved_deadlines = mock_save.call_args[0][0]
        assert "2025-12-15" in saved_deadlines[0]["deadline"]  # Current year

    @patch("schedule_management.reminder.save_deadlines")
    @patch("schedule_management.reminder.load_deadlines")
    @patch("schedule_management.reminder.datetime")
    def test_add_deadline_update_existing(self, mock_datetime, mock_load, mock_save):
        """Test updating an existing deadline."""
        mock_now = MagicMock()
        mock_now.date.return_value = datetime(2025, 11, 22).date()
        mock_now.year = 2025
        mock_datetime.now.return_value = mock_now
        mock_datetime.side_effect = lambda *args, **kw: datetime(*args, **kw)

        existing = [
            {
                "event": "homework2",
                "deadline": "2026-07-04",
                "added": "2025-11-20T10:00:00Z",
            }
        ]
        mock_load.return_value = existing

        args = MagicMock()
        args.event = "homework2"
        args.date = "7.10"  # Change to July 10th

        with patch("builtins.print") as mock_print:
            result = reminder.add_deadline(args)

        assert result == 0
        saved_deadlines = mock_save.call_args[0][0]
        assert len(saved_deadlines) == 1
        assert saved_deadlines[0]["deadline"] == "2026-07-10"
        # Check for update message
        assert "updated" in mock_print.call_args[0][0].lower()

    def test_add_deadline_invalid_format(self):
        """Test adding deadline with invalid date format."""
        args = MagicMock()
        args.event = "homework2"
        args.date = "2026-07-04"  # Wrong format

        with patch("builtins.print") as mock_print:
            result = reminder.add_deadline(args)

        assert result == 1
        mock_print.assert_called_once()
        assert "❌" in mock_print.call_args[0][0]
        assert "format" in mock_print.call_args[0][0].lower()

    def test_add_deadline_invalid_month(self):
        """Test adding deadline with invalid month."""
        args = MagicMock()
        args.event = "homework2"
        args.date = "13.4"  # Month 13 doesn't exist

        with patch("builtins.print") as mock_print:
            result = reminder.add_deadline(args)

        assert result == 1
        assert "❌" in mock_print.call_args[0][0]
        assert "Month must be between 1 and 12" in mock_print.call_args[0][0]

    def test_add_deadline_invalid_day(self):
        """Test adding deadline with invalid day."""
        args = MagicMock()
        args.event = "homework2"
        args.date = "7.32"  # Day 32 doesn't exist

        with patch("builtins.print") as mock_print:
            result = reminder.add_deadline(args)

        assert result == 1
        assert "❌" in mock_print.call_args[0][0]
        assert "Day must be between 1 and 31" in mock_print.call_args[0][0]

    @patch("schedule_management.reminder.save_deadlines")
    @patch("schedule_management.reminder.load_deadlines")
    @patch("schedule_management.reminder.datetime")
    def test_add_deadline_save_error(self, mock_datetime, mock_load, mock_save):
        """Test handling error when saving deadline fails."""
        mock_now = MagicMock()
        mock_now.date.return_value = datetime(2025, 11, 22).date()
        mock_now.year = 2025
        mock_datetime.now.return_value = mock_now
        mock_datetime.side_effect = lambda *args, **kw: datetime(*args, **kw)

        mock_load.return_value = []
        mock_save.side_effect = Exception("Save failed")

        args = MagicMock()
        args.event = "homework2"
        args.date = "7.4"

        with patch("builtins.print") as mock_print:
            result = reminder.add_deadline(args)

        assert result == 1
        assert "❌ Error saving deadline:" in mock_print.call_args[0][0]

    @patch("schedule_management.reminder.save_deadlines")
    @patch("schedule_management.reminder.load_deadlines")
    @patch("schedule_management.reminder.datetime")
    def test_add_deadline_with_leading_zeros(self, mock_datetime, mock_load, mock_save):
        """Test adding deadline with leading zeros in date."""
        mock_now = MagicMock()
        mock_now.date.return_value = datetime(2025, 11, 22).date()
        mock_now.year = 2025
        mock_datetime.now.return_value = mock_now
        mock_datetime.side_effect = lambda *args, **kw: datetime(*args, **kw)

        mock_load.return_value = []

        args = MagicMock()
        args.event = "exam"
        args.date = "07.04"  # With leading zeros

        with patch("builtins.print"):
            result = reminder.add_deadline(args)

        assert result == 0
        saved_deadlines = mock_save.call_args[0][0]
        assert saved_deadlines[0]["deadline"] == "2026-07-04"


class TestDeleteDeadline:
    """Test the delete_deadline command functionality."""

    @patch("schedule_management.reminder.save_deadlines")
    @patch("schedule_management.reminder.load_deadlines")
    def test_delete_deadline_success(self, mock_load, mock_save):
        """Test deleting a deadline successfully."""
        existing = [
            {
                "event": "homework2",
                "deadline": "2026-07-04",
                "added": "2025-11-22T10:00:00Z",
            },
            {
                "event": "project",
                "deadline": "2025-12-25",
                "added": "2025-11-22T11:00:00Z",
            },
        ]
        mock_load.return_value = existing

        args = MagicMock()
        args.events = ["homework2"]

        with patch("builtins.print") as mock_print:
            result = reminder.delete_deadline(args)

        assert result == 0
        mock_save.assert_called_once()
        saved_deadlines = mock_save.call_args[0][0]
        assert len(saved_deadlines) == 1
        assert saved_deadlines[0]["event"] == "project"
        mock_print.assert_called_once()
        assert "✅" in mock_print.call_args[0][0]
        assert "homework2" in mock_print.call_args[0][0]

    @patch("schedule_management.reminder.save_deadlines")
    @patch("schedule_management.reminder.load_deadlines")
    def test_delete_multiple_deadlines(self, mock_load, mock_save):
        """Test deleting multiple deadlines at once."""
        existing = [
            {
                "event": "homework2",
                "deadline": "2026-07-04",
                "added": "2025-11-22T10:00:00Z",
            },
            {
                "event": "project",
                "deadline": "2025-12-25",
                "added": "2025-11-22T11:00:00Z",
            },
            {
                "event": "exam",
                "deadline": "2026-03-15",
                "added": "2025-11-22T12:00:00Z",
            },
        ]
        mock_load.return_value = existing

        args = MagicMock()
        args.events = ["homework2", "exam"]

        with patch("builtins.print"):
            result = reminder.delete_deadline(args)

        assert result == 0
        saved_deadlines = mock_save.call_args[0][0]
        assert len(saved_deadlines) == 1
        assert saved_deadlines[0]["event"] == "project"

    @patch("schedule_management.reminder.load_deadlines")
    def test_delete_deadline_not_found(self, mock_load):
        """Test deleting a non-existent deadline."""
        existing = [
            {
                "event": "homework2",
                "deadline": "2026-07-04",
                "added": "2025-11-22T10:00:00Z",
            }
        ]
        mock_load.return_value = existing

        args = MagicMock()
        args.events = ["nonexistent"]

        with patch("builtins.print") as mock_print:
            result = reminder.delete_deadline(args)

        assert result == 1
        mock_print.assert_called_once()
        assert "❌" in mock_print.call_args[0][0]
        assert "not found" in mock_print.call_args[0][0]

    @patch("schedule_management.reminder.load_deadlines")
    def test_delete_deadline_empty_list(self, mock_load):
        """Test deleting from empty deadline list."""
        mock_load.return_value = []

        args = MagicMock()
        args.events = ["homework2"]

        with patch("builtins.print") as mock_print:
            result = reminder.delete_deadline(args)

        assert result == 1
        mock_print.assert_called_once()
        assert "⚠️" in mock_print.call_args[0][0]
        assert "No deadlines found" in mock_print.call_args[0][0]

    @patch("schedule_management.reminder.save_deadlines")
    @patch("schedule_management.reminder.load_deadlines")
    def test_delete_deadline_partial_success(self, mock_load, mock_save):
        """Test deleting multiple deadlines with some failures."""
        existing = [
            {
                "event": "homework2",
                "deadline": "2026-07-04",
                "added": "2025-11-22T10:00:00Z",
            },
            {
                "event": "project",
                "deadline": "2025-12-25",
                "added": "2025-11-22T11:00:00Z",
            },
        ]
        mock_load.return_value = existing

        args = MagicMock()
        args.events = ["homework2", "nonexistent", "project"]

        with patch("builtins.print") as mock_print:
            result = reminder.delete_deadline(args)

        assert result == 1  # Returns 1 due to partial failure
        saved_deadlines = mock_save.call_args[0][0]
        assert len(saved_deadlines) == 0
        # Check that error was printed
        calls = [str(call) for call in mock_print.call_args_list]
        assert any("nonexistent" in call and "not found" in call for call in calls)

    @patch("schedule_management.reminder.save_deadlines")
    @patch("schedule_management.reminder.load_deadlines")
    def test_delete_deadline_save_error(self, mock_load, mock_save):
        """Test handling error when saving after deletion fails."""
        existing = [
            {
                "event": "homework2",
                "deadline": "2026-07-04",
                "added": "2025-11-22T10:00:00Z",
            }
        ]
        mock_load.return_value = existing
        mock_save.side_effect = Exception("Save failed")

        args = MagicMock()
        args.events = ["homework2"]

        with patch("builtins.print") as mock_print:
            result = reminder.delete_deadline(args)

        assert result == 1
        mock_print.assert_called_once()
        assert "❌ Error saving deadlines:" in mock_print.call_args[0][0]


class TestShowDeadlines:
    """Test the show_deadlines command functionality."""

    @patch("schedule_management.reminder.load_deadlines")
    def test_show_deadlines_empty(self, mock_load):
        """Test showing deadlines when list is empty."""
        mock_load.return_value = []

        args = MagicMock()

        with patch("schedule_management.reminder.Console") as mock_console_class:
            mock_console = MagicMock()
            mock_console_class.return_value = mock_console

            result = reminder.show_deadlines(args)

        assert result == 0
        mock_console.print.assert_called_once()
        call_args = str(mock_console.print.call_args)
        assert "No deadlines found" in call_args or "📅" in call_args

    @patch("schedule_management.reminder.load_deadlines")
    @patch("schedule_management.reminder.datetime")
    def test_show_deadlines_with_data(self, mock_datetime, mock_load):
        """Test showing deadlines with data."""
        mock_now = MagicMock()
        mock_now.date.return_value = datetime(2025, 11, 22).date()
        mock_datetime.now.return_value = mock_now
        mock_datetime.strptime.side_effect = datetime.strptime

        test_deadlines = [
            {
                "event": "homework2",
                "deadline": "2026-07-04",
                "added": "2025-11-22T10:00:00Z",
            },
            {
                "event": "project",
                "deadline": "2025-12-25",
                "added": "2025-11-22T11:00:00Z",
            },
        ]
        mock_load.return_value = test_deadlines

        args = MagicMock()

        with patch("schedule_management.reminder.Console") as mock_console_class:
            mock_console = MagicMock()
            mock_console_class.return_value = mock_console

            result = reminder.show_deadlines(args)

        assert result == 0
        # Should print table and summary
        assert mock_console.print.call_count >= 2

    @patch("schedule_management.reminder.load_deadlines")
    @patch("schedule_management.reminder.datetime")
    def test_show_deadlines_sorted_by_date(self, mock_datetime, mock_load):
        """Test that deadlines are displayed sorted by date."""
        mock_now = MagicMock()
        mock_now.date.return_value = datetime(2025, 11, 22).date()
        mock_datetime.now.return_value = mock_now
        mock_datetime.strptime.side_effect = datetime.strptime

        test_deadlines = [
            {
                "event": "later",
                "deadline": "2026-12-25",
                "added": "2025-11-22T10:00:00Z",
            },
            {
                "event": "sooner",
                "deadline": "2025-12-01",
                "added": "2025-11-22T11:00:00Z",
            },
            {
                "event": "middle",
                "deadline": "2026-06-15",
                "added": "2025-11-22T12:00:00Z",
            },
        ]
        mock_load.return_value = test_deadlines

        args = MagicMock()

        with patch("schedule_management.reminder.Console") as mock_console_class:
            mock_console = MagicMock()
            mock_console_class.return_value = mock_console

            result = reminder.show_deadlines(args)

        assert result == 0
        # Verify table was created (should be in print calls)
        assert mock_console.print.call_count >= 2

    @patch("schedule_management.reminder.load_deadlines")
    @patch("schedule_management.reminder.datetime")
    def test_show_deadlines_urgency_status(self, mock_datetime, mock_load):
        """Test deadline urgency status calculations."""
        # Set current date to November 22, 2025
        mock_now = MagicMock()
        mock_now.date.return_value = datetime(2025, 11, 22).date()
        mock_datetime.now.return_value = mock_now
        mock_datetime.strptime.side_effect = datetime.strptime

        test_deadlines = [
            {
                "event": "urgent",
                "deadline": "2025-11-24",
                "added": "2025-11-22T10:00:00Z",
            },  # 2 days
            {
                "event": "soon",
                "deadline": "2025-11-27",
                "added": "2025-11-22T11:00:00Z",
            },  # 5 days
            {
                "event": "ok",
                "deadline": "2025-12-15",
                "added": "2025-11-22T12:00:00Z",
            },  # 23 days
            {
                "event": "overdue",
                "deadline": "2025-11-20",
                "added": "2025-11-22T13:00:00Z",
            },  # -2 days
        ]
        mock_load.return_value = test_deadlines

        args = MagicMock()

        with patch("schedule_management.reminder.Console") as mock_console_class:
            mock_console = MagicMock()
            mock_console_class.return_value = mock_console

            result = reminder.show_deadlines(args)

        assert result == 0
        # Verify console was used to print the table
        assert mock_console.print.call_count >= 2


class TestGetDdlPath:
    """Test the get_ddl_path helper function."""

    @patch("schedule_management.reminder.get_config_dir")
    def test_get_ddl_path(self, mock_get_config_dir):
        """Test getting the deadline JSON path."""
        mock_get_config_dir.return_value = "/test/config"

        path = reminder.get_ddl_path()

        assert isinstance(path, Path)
        assert str(path) == "/test/config/ddl.json"

    @patch("schedule_management.reminder.get_config_dir")
    def test_get_ddl_path_with_test_config(self, mock_get_config_dir):
        """Test getting the deadline JSON path with test config directory."""
        mock_get_config_dir.return_value = str(TEST_CONFIG_DIR)

        path = reminder.get_ddl_path()

        assert isinstance(path, Path)
        assert "ddl.json" in str(path)


class TestDeadlineIntegration:
    """Integration tests for deadline management workflow."""

    def setup_method(self):
        """Set up test fixtures."""
        self.test_ddl_file = TEST_CONFIG_DIR / "ddl.json"
        self.original_content = None

        if self.test_ddl_file.exists():
            with open(self.test_ddl_file, "r", encoding="utf-8") as f:
                self.original_content = f.read()

    def teardown_method(self):
        """Clean up after tests."""
        if self.original_content is not None:
            with open(self.test_ddl_file, "w", encoding="utf-8") as f:
                f.write(self.original_content)
        elif self.test_ddl_file.exists():
            self.test_ddl_file.unlink()


if __name__ == "__main__":
    import pytest

    pytest.main([__file__, "-v"])
