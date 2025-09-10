import pytest
from datetime import time
from unittest.mock import patch

from schedule_management.reminder_macos import (
    parse_time,
    time_to_str,
    add_minutes_to_time,
    get_today_schedule,
)


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



class TestSchedulerLogic:
    def setup_method(self, method):
        """Execute before each test method runs"""
        self.settings = {
            "sound_file": "/mock/sound.aiff",
            "alarm_interval": 5,
            "max_alarm_duration": 300,
        }
        self.time_blocks = {"pomodoro": 25, "break": 5}
        self.time_points = {
            "go_to_bed": "上床睡觉 😴 该休息了！",
            "summary": "今天的工作结束 🎉, 总结一下",
        }
        self.today_schedule = {
            "08:30": "pomodoro",  # 字符串 time_block
            "09:10": {"block": "pomodoro", "title": "写代码"},  # 字典 time_block
            "10:00": "该喝水了",  # 直接消息
            "21:00": "summary",  # time_point
        }
        self.notified_today = set()
        self.pending_end_alarms = {}

    def simulate_tick(self, current_time_str):
        """Simulate a single time point check in the main loop"""
        if current_time_str == "00:00":
            self.notified_today.clear()
            self.pending_end_alarms.clear()

        # Process start events
        if (
            current_time_str in self.today_schedule
            and current_time_str not in self.notified_today
        ):
            event = self.today_schedule[current_time_str]
            self.notified_today.add(current_time_str)

            if isinstance(event, str):
                if event in self.time_blocks:
                    duration = self.time_blocks[event]
                    end_time_str = add_minutes_to_time(current_time_str, duration)
                    end_message = f"{event} 结束！休息一下 🎉"
                    self.pending_end_alarms[end_time_str] = end_message
                    return {
                        "type": "string_block_start",
                        "block": event,
                        "duration": duration,
                        "end_time": end_time_str,
                    }
                elif event in self.time_points:
                    message = self.time_points[event]
                    return {"type": "time_point", "message": message}
                else:
                    return {"type": "direct_message", "message": event}

            elif isinstance(event, dict) and "block" in event:
                block_type = event["block"]
                title = event.get("title", block_type)
                if block_type not in self.time_blocks:
                    return {"type": "error", "message": f"Unknown block: {block_type}"}
                duration = self.time_blocks[block_type]
                end_time_str = add_minutes_to_time(current_time_str, duration)
                end_message = f"{title} 结束！休息一下 🎉"
                self.pending_end_alarms[end_time_str] = end_message
                return {
                    "type": "dict_block_start",
                    "title": title,
                    "duration": duration,
                    "end_time": end_time_str,
                }

        # Process pending end alarms
        if (
            current_time_str in self.pending_end_alarms
            and current_time_str not in self.notified_today
        ):
            message = self.pending_end_alarms[current_time_str]
            self.notified_today.add(current_time_str)
            del self.pending_end_alarms[current_time_str]
            return {"type": "block_end", "message": message}

        return {"type": "idle"}

    def test_string_block_event_schedules_end_alarm(self):
        """测试字符串类型的 time_block 事件"""
        result = self.simulate_tick("08:30")
        assert result["type"] == "string_block_start"
        assert result["block"] == "pomodoro"
        assert result["duration"] == 25
        assert result["end_time"] == "08:55"
        assert "08:30" in self.notified_today
        assert "08:55" in self.pending_end_alarms
        assert self.pending_end_alarms["08:55"] == "pomodoro 结束！休息一下 🎉"

    def test_time_point_event_triggers_correct_message(self):
        """测试 time_point 事件触发一次性提醒"""
        result = self.simulate_tick("21:00")
        assert result["type"] == "time_point"
        assert result["message"] == "今天的工作结束 🎉, 总结一下"
        assert "21:00" in self.notified_today
        assert len(self.pending_end_alarms) == 0  # time_point 不应安排结束提醒

    def test_direct_message_event_triggers_alarm(self):
        """测试直接消息字符串触发一次性提醒"""
        result = self.simulate_tick("10:00")
        assert result["type"] == "direct_message"
        assert result["message"] == "该喝水了"
        assert "10:00" in self.notified_today
        assert len(self.pending_end_alarms) == 0  # 直接消息不应安排结束提醒

    def test_dict_block_start_schedules_end_alarm(self):
        result = self.simulate_tick("09:10")
        assert result["type"] == "dict_block_start"
        assert result["title"] == "写代码"
        assert result["duration"] == 25
        assert result["end_time"] == "09:35"
        assert "09:10" in self.notified_today
        assert "09:35" in self.pending_end_alarms

    def test_block_end_triggered_at_correct_time(self):
        self.simulate_tick("09:10")  # 启动一个 pomodoro
        result = self.simulate_tick("09:35")
        assert result["type"] == "block_end"
        assert result["message"] == "写代码 结束！休息一下 🎉"
        assert "09:35" in self.notified_today
        assert "09:35" not in self.pending_end_alarms

    def test_no_duplicate_alarms(self):
        self.simulate_tick("09:10")
        result = self.simulate_tick("09:10")
        assert result["type"] == "idle"

    def test_midnight_resets_state(self):
        self.simulate_tick("08:30")  # 触发一个事件
        assert len(self.notified_today) > 0
        assert len(self.pending_end_alarms) > 0

        self.simulate_tick("00:00")  # 午夜重置

        assert len(self.notified_today) == 0
        assert len(self.pending_end_alarms) == 0


class TestFullFlow:
    def setup_method(self, method):
        self.schedule = {
            "09:00": {"block": "pomodoro", "title": "Focus Task A"},
            "10:00": {"block": "pomodoro", "title": "Focus Task B"},
            "11:00": "Lunch time 🍜",
        }
        self.time_blocks = {"pomodoro": 25, "break": 5}
        self.notified_today = set()
        self.pending_end_alarms = {}

    def simulate_tick(self, time_str):
        if time_str == "00:00":
            self.notified_today.clear()
            self.pending_end_alarms.clear()
            return "RESET"

        if time_str in self.schedule and time_str not in self.notified_today:
            event = self.schedule[time_str]
            if isinstance(event, str):
                self.notified_today.add(time_str)
                return f"string event: {event}"
            elif isinstance(event, dict):
                block = event["block"]
                if block not in self.time_blocks:
                    return f"ERROR: unknown block {block}"
                duration = self.time_blocks[block]
                end_time = add_minutes_to_time(time_str, duration)
                self.notified_today.add(time_str)
                end_msg = f"{event['title']} finished!"
                self.pending_end_alarms[end_time] = end_msg
                return f"START: {event['title']} ({duration}min) → ends at {end_time}"

        if time_str in self.pending_end_alarms and time_str not in self.notified_today:
            msg = self.pending_end_alarms[time_str]
            self.notified_today.add(time_str)
            del self.pending_end_alarms[time_str]
            return f"END: {msg}"

        return "IDLE"

    def test_full_day_flow(self):
        events = [
            self.simulate_tick("08:59"),
            self.simulate_tick("09:00"),
            self.simulate_tick("09:10"),
            self.simulate_tick("09:25"),
            self.simulate_tick("11:00"),
            self.simulate_tick("00:00"),
            self.simulate_tick("09:00"),
        ]

        expected_sequence = [
            "IDLE",
            "START: Focus Task A (25min) → ends at 09:25",
            "IDLE",
            "END: Focus Task A finished!",
            "string event: Lunch time 🍜",
            "RESET",
            "START: Focus Task A (25min) → ends at 09:25",
        ]

        assert events == expected_sequence
