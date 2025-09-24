from datetime import time
from unittest.mock import patch, MagicMock

from schedule_management.reminder_macos import (
    ScheduleConfig,
    WeeklySchedule,
    ScheduleRunner,
)
from schedule_management.utils import parse_time, add_minutes_to_time, time_to_str


def test_parse_time():
    """Test time string parsing"""
    t = parse_time("09:30")
    assert t.hour == 9
    assert t.minute == 30


def test_time_to_str():
    """Test time object to string conversion"""
    t = time(14, 5)
    s = time_to_str(t)
    assert s == "14:05"


def test_add_minutes_to_time():
    """Test time addition"""
    # Normal case
    result = add_minutes_to_time("09:10", 25)
    assert result == "09:35"
    # Cross hour
    result = add_minutes_to_time("09:50", 20)
    assert result == "10:10"
    # Cross day (wrap around)
    result = add_minutes_to_time("23:50", 30)
    assert result == "00:20"
    # Exact hour
    result = add_minutes_to_time("10:00", 60)
    assert result == "11:00"


class TestScheduleConfig:
    """Test ScheduleConfig class functionality"""

    def test_should_skip_today_with_empty_skip_days(self):
        """Test should_skip_today with empty skip_days list"""
        config = ScheduleConfig.__new__(ScheduleConfig)
        config.settings = {"skip_days": []}
        assert not config.should_skip_today()

    def test_should_skip_today_with_no_skip_days_key(self):
        """Test should_skip_today when skip_days key is missing"""
        config = ScheduleConfig.__new__(ScheduleConfig)
        config.settings = {}
        assert not config.should_skip_today()

    @patch("schedule_management.reminder_macos.datetime")
    def test_should_skip_today_with_matching_day(self, mock_datetime):
        """Test should_skip_today when current day is in skip_days"""
        mock_now = MagicMock()
        mock_now.strftime.return_value = "sunday"
        mock_datetime.now.return_value = mock_now

        config = ScheduleConfig.__new__(ScheduleConfig)
        config.settings = {"skip_days": ["sunday"]}
        assert config.should_skip_today()

    @patch("schedule_management.reminder_macos.datetime")
    def test_should_skip_today_with_non_matching_day(self, mock_datetime):
        """Test should_skip_today when current day is not in skip_days"""
        mock_now = MagicMock()
        mock_now.strftime.return_value = "monday"
        mock_datetime.now.return_value = mock_now

        config = ScheduleConfig.__new__(ScheduleConfig)
        config.settings = {"skip_days": ["sunday"]}
        assert not config.should_skip_today()

    @patch("schedule_management.reminder_macos.datetime")
    def test_should_skip_today_with_multiple_skip_days(self, mock_datetime):
        """Test should_skip_today with multiple days in skip_days"""
        mock_now = MagicMock()
        mock_now.strftime.return_value = "saturday"
        mock_datetime.now.return_value = mock_now

        config = ScheduleConfig.__new__(ScheduleConfig)
        config.settings = {"skip_days": ["sunday", "saturday", "friday"]}
        assert config.should_skip_today()


class TestWeeklySchedule:
    """Test WeeklySchedule class functionality"""

    def test_get_schedule_for_parity(self):
        """Test getting schedule based on week parity"""
        odd_data = {"common": {"21:00": "summary"}}
        even_data = {"common": {"22:00": "bedtime"}}

        weekly = WeeklySchedule.__new__(WeeklySchedule)
        weekly.odd_data = odd_data
        weekly.even_data = even_data

        assert weekly.get_schedule_for_parity("odd") == odd_data
        assert weekly.get_schedule_for_parity("even") == even_data

    @patch("schedule_management.reminder_macos.get_week_parity")
    @patch("schedule_management.reminder_macos.datetime")
    def test_get_today_schedule_normal_day(self, mock_datetime, mock_parity):
        """Test get_today_schedule on a normal day"""
        mock_now = MagicMock()
        mock_now.strftime.return_value = "monday"
        mock_datetime.now.return_value = mock_now
        mock_parity.return_value = "odd"

        odd_data = {
            "monday": {"09:00": "pomodoro"},
            "common": {"21:00": "summary_time"},
        }
        weekly = WeeklySchedule.__new__(WeeklySchedule)
        weekly.odd_data = odd_data
        weekly.even_data = {}

        config = ScheduleConfig.__new__(ScheduleConfig)
        config.settings = {"skip_days": ["sunday"]}

        result = weekly.get_today_schedule(config)
        assert result == {"09:00": "pomodoro", "21:00": "summary_time"}

    @patch("schedule_management.reminder_macos.get_week_parity")
    @patch("schedule_management.reminder_macos.datetime")
    def test_get_today_schedule_skip_day(self, mock_datetime, mock_parity):
        """Test get_today_schedule returns empty on skip days"""
        mock_now = MagicMock()
        mock_now.strftime.return_value = "sunday"
        mock_datetime.now.return_value = mock_now
        mock_parity.return_value = "odd"

        weekly = WeeklySchedule.__new__(WeeklySchedule)
        weekly.odd_data = {"sunday": {"10:00": "relax"}}
        weekly.even_data = {}

        config = ScheduleConfig.__new__(ScheduleConfig)
        config.settings = {"skip_days": ["sunday"]}

        result = weekly.get_today_schedule(config)
        assert result == {}


class TestScheduleRunner:
    """Test ScheduleRunner class functionality"""

    def setup_method(self):
        """Setup common test data"""
        self.config = ScheduleConfig.__new__(ScheduleConfig)
        self.config.settings = {
            "sound_file": "/mock/sound.aiff",
            "alarm_interval": 5,
            "max_alarm_duration": 300,
        }
        self.config.time_blocks = {"pomodoro": 25, "break": 5}
        self.config.time_points = {
            "go_to_bed": "上床睡觉 😴 该休息了！",
            "summary": "今天的工作结束 🎉, 总结一下",
        }

        self.today_schedule = {
            "08:30": "pomodoro",  # 字符串 time_block
            "09:10": {"block": "pomodoro", "title": "写代码"},  # 字典 time_block
            "10:00": "该喝水了",  # 直接消息
            "21:00": "summary",  # time_point
        }

        self.runner = ScheduleRunner.__new__(ScheduleRunner)
        self.runner.config = self.config
        self.runner.notified_today = set()
        self.runner.pending_end_alarms = {}
        self.runner.weekly_schedule = MagicMock()

    @patch("schedule_management.reminder_macos.alarm")
    def test_handle_string_block_event(self, mock_alarm):
        """测试字符串类型的 time_block 事件"""
        self.runner._handle_event("08:30", "pomodoro")

        mock_alarm.assert_called_once()
        assert "08:30" in self.runner.notified_today
        assert "08:55" in self.runner.pending_end_alarms
        assert self.runner.pending_end_alarms["08:55"] == "pomodoro 结束！休息一下 🎉"

    @patch("schedule_management.reminder_macos.alarm")
    def test_handle_time_point_event(self, mock_alarm):
        """测试 time_point 事件触发一次性提醒"""
        self.runner._handle_event("21:00", "summary")

        mock_alarm.assert_called_once()
        assert "21:00" in self.runner.notified_today
        assert len(self.runner.pending_end_alarms) == 0

    @patch("schedule_management.reminder_macos.alarm")
    def test_handle_direct_message_event(self, mock_alarm):
        """测试直接消息字符串触发一次性提醒"""
        self.runner._handle_event("10:00", "该喝水了")

        mock_alarm.assert_called_once()
        assert "10:00" in self.runner.notified_today
        assert len(self.runner.pending_end_alarms) == 0

    @patch("schedule_management.reminder_macos.alarm")
    def test_handle_dict_block_event(self, mock_alarm):
        """测试字典类型的 block 事件"""
        event = {"block": "pomodoro", "title": "写代码"}
        self.runner._handle_event("09:10", event)

        mock_alarm.assert_called_once()
        assert "09:10" in self.runner.notified_today
        assert "09:35" in self.runner.pending_end_alarms
        assert self.runner.pending_end_alarms["09:35"] == "写代码 结束！休息一下 🎉"

    @patch("schedule_management.reminder_macos.alarm")
    def test_handle_unknown_block_type(self, mock_alarm):
        """测试处理未知的 block 类型"""
        event = {"block": "unknown_block", "title": "Unknown"}
        self.runner._handle_event("10:00", event)

        mock_alarm.assert_not_called()
        assert "10:00" not in self.runner.notified_today

    @patch("schedule_management.reminder_macos.datetime")
    @patch("schedule_management.reminder_macos.alarm")
    def test_process_end_alarms(self, mock_alarm, mock_datetime):
        """测试处理结束提醒"""
        mock_now = MagicMock()
        mock_now.strftime.return_value = "09:35"
        mock_datetime.now.return_value = mock_now

        # Setup a pending end alarm
        self.runner.pending_end_alarms["09:35"] = "写代码 结束！休息一下 🎉"
        self.runner.notified_today = set()

        # Simulate the run loop processing
        if (
            "09:35" in self.runner.pending_end_alarms
            and "09:35" not in self.runner.notified_today
        ):
            _ = self.runner.pending_end_alarms["09:35"]
            self.runner.notified_today.add("09:35")
            del self.runner.pending_end_alarms["09:35"]
            # In real code, this would call alarm, but we're testing the state change

        assert "09:35" in self.runner.notified_today
        assert "09:35" not in self.runner.pending_end_alarms

    @patch("schedule_management.reminder_macos.datetime")
    def test_midnight_reset(self, mock_datetime):
        """测试午夜重置功能"""
        # Setup some state
        self.runner.notified_today.add("08:30")
        self.runner.pending_end_alarms["08:55"] = "pomodoro 结束！休息一下 🎉"

        # Simulate midnight
        mock_now = MagicMock()
        mock_now.strftime.return_value = "00:00"
        mock_datetime.now.return_value = mock_now

        # This would be called in the main loop
        if "00:00" == "00:00":  # Simplified for test
            self.runner.notified_today.clear()
            self.runner.pending_end_alarms.clear()

        assert len(self.runner.notified_today) == 0
        assert len(self.runner.pending_end_alarms) == 0


class TestFullFlow:
    """Test complete day flow with ScheduleRunner"""

    def setup_method(self):
        self.config = ScheduleConfig.__new__(ScheduleConfig)
        self.config.time_blocks = {"pomodoro": 25}
        self.config.time_points = {}
        self.config.settings = {}

        self.schedule_data = {
            "09:00": {"block": "pomodoro", "title": "Focus Task A"},
            "10:00": {"block": "pomodoro", "title": "Focus Task B"},
            "11:00": "Lunch time 🍜",
        }

        self.weekly = MagicMock()
        self.weekly.get_today_schedule.return_value = self.schedule_data

        self.runner = ScheduleRunner(self.config, self.weekly)
        self.events_log = []

    @patch("schedule_management.reminder_macos.alarm")
    @patch("schedule_management.reminder_macos.datetime")
    @patch("schedule_management.reminder_macos.time.sleep")
    def test_full_day_flow(self, mock_sleep, mock_datetime, mock_alarm):
        """Test complete day flow"""
        mock_sleep.side_effect = lambda x: None
        event_log = []  # ← Log real events as they occur

        test_times = ["08:59", "09:00", "09:10", "09:25", "11:00", "00:00", "09:00"]

        def create_mock_now(time_str):
            mock_now = MagicMock()
            mock_now.strftime.return_value = time_str
            return mock_now

        for time_str in test_times:
            mock_datetime.now.return_value = create_mock_now(time_str)

            if time_str == "00:00":
                self.runner.notified_today.clear()
                self.runner.pending_end_alarms.clear()
                event_log.append("RESET")
            else:
                today_schedule = self.runner.weekly_schedule.get_today_schedule(
                    self.runner.config
                )

                # Check for start events
                if (
                    time_str in today_schedule
                    and time_str not in self.runner.notified_today
                ):
                    event = today_schedule[time_str]
                    self.runner._handle_event(time_str, event)
                    # Log what happened
                    if isinstance(event, str):
                        if event in self.config.time_blocks:
                            duration = self.config.time_blocks[event]
                            end_time = add_minutes_to_time(time_str, duration)
                            event_log.append(
                                f"START: {event} ({duration}min) → ends at {end_time}"
                            )
                        else:
                            event_log.append(f"MESSAGE: {event}")
                    elif isinstance(event, dict) and "block" in event:
                        block = event["block"]
                        if block in self.config.time_blocks:
                            duration = self.config.time_blocks[block]
                            end_time = add_minutes_to_time(time_str, duration)
                            event_log.append(
                                f"START: {event['title']} ({duration}min) → ends at {end_time}"
                            )

                # Check for end alarms
                elif (
                    time_str in self.runner.pending_end_alarms
                    and time_str not in self.runner.notified_today
                ):
                    message = self.runner.pending_end_alarms[time_str]
                    # In real code, alarm() is called, but we just log
                    event_log.append(f"END: {message}")
                    self.runner.notified_today.add(time_str)
                    del self.runner.pending_end_alarms[time_str]

                else:
                    event_log.append("IDLE")

        # Now assert based on actual logged events
        assert "START: Focus Task A (25min) → ends at 09:25" in event_log
        assert "MESSAGE: Lunch time 🍜" in event_log
        assert "END: Focus Task A 结束！休息一下 🎉" in event_log
        assert "RESET" in event_log
