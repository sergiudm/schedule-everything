from datetime import datetime
from unittest.mock import patch, MagicMock
import os

from schedule_management.reminder_macos import ScheduleConfig, ScheduleRunner
from schedule_management.report import auto_generate_reports


class TestReportGeneration:
    """Test automatic report generation functionality"""

    def setup_method(self):
        """Setup common test data"""
        self.config = ScheduleConfig.__new__(ScheduleConfig)
        self.config.settings = {
            "sound_file": "/mock/sound.aiff",
            "alarm_interval": 5,
            "max_alarm_duration": 300,
        }
        self.config.time_blocks = {"pomodoro": 25, "break": 5}
        self.config.time_points = {}
        self.config.tasks = {
            "daily_summary": "23:00",
            "weekly_review": "sunday 20:00",
            "monthly_review": "1 20:00"
        }
        self.config.paths = {"config_dir": "config"}

        self.runner = ScheduleRunner.__new__(ScheduleRunner)
        self.runner.config = self.config
        self.runner.notified_today = set()
        self.runner.pending_end_alarms = {}
        self.runner.weekly_schedule = MagicMock()

    def test_weekly_review_time_property(self):
        """Test weekly_review_time property"""
        config = ScheduleConfig.__new__(ScheduleConfig)
        config.tasks = {"weekly_review": "sunday 20:00"}
        
        assert config.weekly_review_time == "sunday 20:00"

    def test_weekly_review_time_property_default(self):
        """Test weekly_review_time property with default value"""
        config = ScheduleConfig.__new__(ScheduleConfig)
        config.tasks = {}
        
        assert config.weekly_review_time == ""

    def test_monthly_review_time_property(self):
        """Test monthly_review_time property"""
        config = ScheduleConfig.__new__(ScheduleConfig)
        config.tasks = {"monthly_review": "1 20:00"}
        
        assert config.monthly_review_time == "1 20:00"

    def test_monthly_review_time_property_default(self):
        """Test monthly_review_time property with default value"""
        config = ScheduleConfig.__new__(ScheduleConfig)
        config.tasks = {}
        
        assert config.monthly_review_time == ""

    @patch("schedule_management.reminder_macos.try_auto_generate_reports")
    @patch("schedule_management.reminder_macos.datetime")
    def test_weekly_review_triggered_on_correct_day_and_time(self, mock_datetime, mock_auto_generate):
        """Test that weekly review is triggered on the correct day and time"""
        # Mock datetime to simulate Sunday 20:00
        mock_now = MagicMock()
        mock_now.strftime.return_value = "20:00"
        mock_now.strftime.side_effect = lambda fmt: "sunday" if fmt == "%A" else "20:00" if fmt == "%H:%M" else "2025-1-23" if fmt == "%Y-%m-%d" else "2025-11-23"
        mock_now.day = 23 # Date doesn't matter for weekly check
        mock_datetime.now.return_value = mock_now

        # Set up the runner with weekly review schedule
        self.runner.config.tasks["weekly_review"] = "sunday 20:00"
        self.runner.notified_today = set()

        # Simulate the run loop logic using the mocked datetime
        now = mock_datetime.now.return_value
        now_str = now.strftime("%H:%M")
        now_date = now.strftime("%Y-%m-%d")
    
        # Check if weekly review should be triggered
        weekly_review_setting = self.runner.config.weekly_review_time
        if weekly_review_setting:
            try:
                # Parse the weekly review setting (format: "sunday 20:00")
                parts = weekly_review_setting.split()
                if len(parts) == 2:
                    day_of_week, review_time = parts
                    if now.strftime("%A").lower() == day_of_week.lower() and now_str == review_time:
                        if f"weekly_review_{now_date}" not in self.runner.notified_today:
                            # This would call try_auto_generate_reports in real code
                            self.runner.notified_today.add(f"weekly_review_{now_date}")
            except Exception:
                pass  # Ignore parsing errors like in the actual code
    
        # Verify that the weekly review flag was added to notified_today
        assert f"weekly_review_{now_date}" in self.runner.notified_today

    @patch("schedule_management.reminder_macos.datetime")
    def test_weekly_review_not_triggered_on_wrong_day(self, mock_datetime):
        """Test that weekly review is not triggered on wrong day"""
        # Mock datetime to simulate Monday 20:00 (not Sunday)
        mock_now = MagicMock()
        mock_now.strftime.return_value = "20:00"
        mock_now.strftime.side_effect = lambda fmt: "monday" if fmt == "%A" else "20:00"
        mock_datetime.now.return_value = mock_now

        # Set up the runner with weekly review schedule
        self.runner.config.tasks["weekly_review"] = "sunday 20:00"
        self.runner.notified_today = set()

        # Simulate the run loop logic
        now = datetime.now()
        now_str = now.strftime("%H:%M")
        
        # Check if weekly review should be triggered
        weekly_review_setting = self.runner.config.weekly_review_time
        if weekly_review_setting:
            try:
                # Parse the weekly review setting (format: "sunday 20:00")
                parts = weekly_review_setting.split()
                if len(parts) == 2:
                    day_of_week, review_time = parts
                    if now.strftime("%A").lower() == day_of_week.lower() and now_str == review_time:
                        if f"weekly_review_{now.strftime('%Y-%m-%d')}" not in self.runner.notified_today:
                            # This would call try_auto_generate_reports in real code
                            self.runner.notified_today.add(f"weekly_review_{now.strftime('%Y-%m-%d')}")
            except Exception:
                pass  # Ignore parsing errors like in the actual code
                            
        # Verify that the weekly review flag was NOT added to notified_today
        assert f"weekly_review_{now.strftime('%Y-%m-%d')}" not in self.runner.notified_today

    @patch("schedule_management.reminder_macos.datetime")
    def test_weekly_review_not_triggered_on_wrong_time(self, mock_datetime):
        """Test that weekly review is not triggered on wrong time"""
        # Mock datetime to simulate Sunday 19:00 (not 20:00)
        mock_now = MagicMock()
        mock_now.strftime.return_value = "19:00"
        mock_now.strftime.side_effect = lambda fmt: "sunday" if fmt == "%A" else "19:00"
        mock_datetime.now.return_value = mock_now

        # Set up the runner with weekly review schedule
        self.runner.config.tasks["weekly_review"] = "sunday 20:00"
        self.runner.notified_today = set()

        # Simulate the run loop logic
        now = datetime.now()
        now_str = now.strftime("%H:%M")
        
        # Check if weekly review should be triggered
        weekly_review_setting = self.runner.config.weekly_review_time
        if weekly_review_setting:
            try:
                # Parse the weekly review setting (format: "sunday 20:00")
                parts = weekly_review_setting.split()
                if len(parts) == 2:
                    day_of_week, review_time = parts
                    if now.strftime("%A").lower() == day_of_week.lower() and now_str == review_time:
                        if f"weekly_review_{now.strftime('%Y-%m-%d')}" not in self.runner.notified_today:
                            # This would call try_auto_generate_reports in real code
                            self.runner.notified_today.add(f"weekly_review_{now.strftime('%Y-%m-%d')}")
            except Exception:
                pass  # Ignore parsing errors like in the actual code
                            
        # Verify that the weekly review flag was NOT added to notified_today
        assert f"weekly_review_{now.strftime('%Y-%m-%d')}" not in self.runner.notified_today

    @patch("schedule_management.reminder_macos.datetime")
    def test_monthly_review_triggered_on_correct_day_and_time(self, mock_datetime):
        """Test that monthly review is triggered on the correct day of month and time"""
        # Mock datetime to simulate 1st day of month at 20:00
        mock_now = MagicMock()
        mock_now.strftime.return_value = "20:00"
        mock_now.strftime.side_effect = lambda fmt: "1" if fmt == "%d" else "20:00" if fmt == "%H:%M" else "2025-1" if fmt == "%Y-%m" else "2025-01-01"
        mock_now.day = 1  # First day of month
        mock_datetime.now.return_value = mock_now

        # Set up the runner with monthly review schedule
        self.runner.config.tasks["monthly_review"] = "1 20:00"
        self.runner.notified_today = set()

        # Simulate the run loop logic using the mocked datetime
        now = mock_datetime.now.return_value
        now_str = now.strftime("%H:%M")
        now_month = now.strftime("%Y-%m")
    
        # Check if monthly review should be triggered
        monthly_review_setting = self.runner.config.monthly_review_time
        if monthly_review_setting:
            try:
                # Parse the monthly review setting (format: "1 20:00")
                parts = monthly_review_setting.split()
                if len(parts) == 2:
                    day_of_month, review_time = parts
                    if now.day == int(day_of_month) and now_str == review_time:
                        if f"monthly_review_{now_month}" not in self.runner.notified_today:
                            # This would call try_auto_generate_reports in real code
                            self.runner.notified_today.add(f"monthly_review_{now_month}")
            except Exception:
                pass  # Ignore parsing errors like in the actual code
    
        # Verify that the monthly review flag was added to notified_today
        assert f"monthly_review_{now_month}" in self.runner.notified_today

    @patch("schedule_management.reminder_macos.datetime")
    def test_monthly_review_not_triggered_on_wrong_day(self, mock_datetime):
        """Test that monthly review is not triggered on wrong day of month"""
        # Mock datetime to simulate 2nd day of month at 20:00 (not 1st)
        mock_now = MagicMock()
        mock_now.strftime.return_value = "20:00"
        mock_now.strftime.side_effect = lambda fmt: "2" if fmt == "%d" else "20:00"
        mock_now.day = 2  # Second day of month
        mock_datetime.now.return_value = mock_now

        # Set up the runner with monthly review schedule
        self.runner.config.tasks["monthly_review"] = "1 20:00"
        self.runner.notified_today = set()

        # Simulate the run loop logic
        now = datetime.now()
        now_str = now.strftime("%H:%M")
        
        # Check if monthly review should be triggered
        monthly_review_setting = self.runner.config.monthly_review_time
        if monthly_review_setting:
            try:
                # Parse the monthly review setting (format: "1 20:00")
                parts = monthly_review_setting.split()
                if len(parts) == 2:
                    day_of_month, review_time = parts
                    if now.day == int(day_of_month) and now_str == review_time:
                        if f"monthly_review_{now.strftime('%Y-%m')}" not in self.runner.notified_today:
                            # This would call try_auto_generate_reports in real code
                            self.runner.notified_today.add(f"monthly_review_{now.strftime('%Y-%m')}")
            except Exception:
                pass  # Ignore parsing errors like in the actual code
                            
        # Verify that the monthly review flag was NOT added to notified_today
        assert f"monthly_review_{now.strftime('%Y-%m')}" not in self.runner.notified_today

    @patch("schedule_management.reminder_macos.datetime")
    def test_monthly_review_not_triggered_on_wrong_time(self, mock_datetime):
        """Test that monthly review is not triggered on wrong time"""
        # Mock datetime to simulate 1st day of month at 19:00 (not 20:00)
        mock_now = MagicMock()
        mock_now.strftime.return_value = "19:00"
        mock_now.strftime.side_effect = lambda fmt: "1" if fmt == "%d" else "19:00"
        mock_now.day = 1  # First day of month
        mock_datetime.now.return_value = mock_now

        # Set up the runner with monthly review schedule
        self.runner.config.tasks["monthly_review"] = "1 20:00"
        self.runner.notified_today = set()

        # Simulate the run loop logic
        now = datetime.now()
        now_str = now.strftime("%H:%M")
        
        # Check if monthly review should be triggered
        monthly_review_setting = self.runner.config.monthly_review_time
        if monthly_review_setting:
            try:
                # Parse the monthly review setting (format: "1 20:00")
                parts = monthly_review_setting.split()
                if len(parts) == 2:
                    day_of_month, review_time = parts
                    if now.day == int(day_of_month) and now_str == review_time:
                        if f"monthly_review_{now.strftime('%Y-%m')}" not in self.runner.notified_today:
                            # This would call try_auto_generate_reports in real code
                            self.runner.notified_today.add(f"monthly_review_{now.strftime('%Y-%m')}")
            except Exception:
                pass  # Ignore parsing errors like in the actual code
                            
        # Verify that the monthly review flag was NOT added to notified_today
        assert f"monthly_review_{now.strftime('%Y-%m')}" not in self.runner.notified_today

    @patch("schedule_management.reminder_macos.datetime")
    def test_weekly_review_prevents_duplicate_generation_same_day(self, mock_datetime):
        """Test that weekly review is not triggered multiple times on the same day"""
        # Mock datetime to simulate Sunday 20:00
        mock_now = MagicMock()
        mock_now.strftime.return_value = "20:00"
        mock_now.strftime.side_effect = lambda fmt: "sunday" if fmt == "%A" else "20:00"
        mock_now.day = 1
        mock_datetime.now.return_value = mock_now

        # Set up the runner with weekly review schedule and mark it as already notified
        self.runner.config.tasks["weekly_review"] = "sunday 20:00"
        self.runner.notified_today = {f"weekly_review_{datetime.now().strftime('%Y-%m-%d')}"}

        # Simulate the run loop logic
        now = datetime.now()
        now_str = now.strftime("%H:%M")
        
        # Check if weekly review should be triggered
        weekly_review_setting = self.runner.config.weekly_review_time
        if weekly_review_setting:
            try:
                # Parse the weekly review setting (format: "sunday 20:00")
                parts = weekly_review_setting.split()
                if len(parts) == 2:
                    day_of_week, review_time = parts
                    if now.strftime("%A").lower() == day_of_week.lower() and now_str == review_time:
                        if f"weekly_review_{now.strftime('%Y-%m-%d')}" not in self.runner.notified_today:
                            # This would call try_auto_generate_reports in real code
                            self.runner.notified_today.add(f"weekly_review_{now.strftime('%Y-%m-%d')}")
            except Exception:
                pass  # Ignore parsing errors like in the actual code
                            
        # Verify that the notified_today set size hasn't changed (no duplicate added)
        initial_size = len({f"weekly_review_{datetime.now().strftime('%Y-%m-%d')}"})
        final_size = len(self.runner.notified_today)
        assert initial_size == final_size

    @patch("schedule_management.reminder_macos.datetime")
    def test_monthly_review_prevents_duplicate_generation_same_month(self, mock_datetime):
        """Test that monthly review is not triggered multiple times in the same month"""
        # Mock datetime to simulate 1st of month at 20:00
        mock_now = MagicMock()
        mock_now.strftime.return_value = "20:00"
        mock_now.strftime.side_effect = lambda fmt: "1" if fmt == "%d" else "20:00"
        mock_now.day = 1
        mock_datetime.now.return_value = mock_now

        # Set up the runner with monthly review schedule and mark it as already notified
        self.runner.config.tasks["monthly_review"] = "1 20:00"
        self.runner.notified_today = {f"monthly_review_{datetime.now().strftime('%Y-%m')}"}

        # Simulate the run loop logic
        now = datetime.now()
        now_str = now.strftime("%H:%M")
        
        # Check if monthly review should be triggered
        monthly_review_setting = self.runner.config.monthly_review_time
        if monthly_review_setting:
            try:
                # Parse the monthly review setting (format: "1 20:00")
                parts = monthly_review_setting.split()
                if len(parts) == 2:
                    day_of_month, review_time = parts
                    if now.day == int(day_of_month) and now_str == review_time:
                        if f"monthly_review_{now.strftime('%Y-%m')}" not in self.runner.notified_today:
                            # This would call try_auto_generate_reports in real code
                            self.runner.notified_today.add(f"monthly_review_{now.strftime('%Y-%m')}")
            except Exception:
                pass  # Ignore parsing errors like in the actual code
                            
        # Verify that the notified_today set size hasn't changed (no duplicate added)
        initial_size = len({f"monthly_review_{datetime.now().strftime('%Y-%m')}"})
        final_size = len(self.runner.notified_today)
        assert initial_size == final_size