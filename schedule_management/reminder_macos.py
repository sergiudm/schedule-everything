import time
import subprocess
import tomllib
from datetime import datetime, timedelta
from pathlib import Path


def load_toml_file(filename):
    """Helper to load a single TOML file"""
    script_dir = Path(__file__).parent
    file_path = script_dir / filename

    if not file_path.exists():
        raise FileNotFoundError(f"Configuration file not found: {file_path}")

    with open(file_path, "rb") as f:
        return tomllib.load(f)


def load_settings(filename="settings.toml"):
    """Load settings from settings.toml"""
    config = load_toml_file(filename=filename)
    settings = config.get("settings", {})
    time_blocks = config.get("time_blocks", {})
    time_points = config.get("time_points", {})
    return settings, time_blocks, time_points


def load_odd_week_schedule():
    """Load odd week schedule from odd_weeks.toml"""
    return load_toml_file("odd_weeks.toml")


def load_even_week_schedule():
    """Load even week schedule from even_weeks.toml"""
    return load_toml_file("even_weeks.toml")


def _play_sound(sound_file):
    """Play system sound using afplay"""
    subprocess.Popen(["afplay", sound_file])


def _show_dialog(message):
    """Show AppleScript dialog with '停止闹铃' button"""
    result = subprocess.run(
        [
            "osascript",
            "-e",
            f'display dialog "{message}" buttons {{"停止闹铃"}} default button "停止闹铃"',
        ],
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def alarm(title, message, sound_file, alarm_interval, max_alarm_duration):
    """Trigger repeating alarm until dismissed or timeout"""
    start_time = time.time()
    while True:
        _play_sound(sound_file)
        button = _show_dialog(message)
        if "停止闹铃" in button:
            break
        if time.time() - start_time > max_alarm_duration:
            break
        time.sleep(alarm_interval)


def get_week_parity():
    """Return 'odd' or 'even' based on ISO calendar week number"""
    week_number = datetime.now().isocalendar().week
    return "odd" if week_number % 2 == 1 else "even"


def get_today_schedule():
    """
    Get today's schedule by merging the day-specific schedule over the common schedule.
    """
    now = datetime.now()
    weekday_en = now.strftime("%A").lower()

    weekday_map = {
        "monday": "monday",
        "tuesday": "tuesday",
        "wednesday": "wednesday",
        "thursday": "thursday",
        "friday": "friday",
        "saturday": "saturday",
        "sunday": "sunday",
    }

    day_key = weekday_map.get(weekday_en)
    if not day_key:
        return {}

    # Load the correct schedule file based on week parity
    parity = get_week_parity()
    if parity == "odd":
        schedule_data = load_odd_week_schedule()
    else:
        schedule_data = load_even_week_schedule()

    # Get the common schedule (defaults to empty dict if not found)
    common_schedule = schedule_data.get("common", {})

    # Get the specific schedule for today (defaults to empty dict if not found)
    day_specific_schedule = schedule_data.get(day_key, {})

    # Merge the schedules. The day-specific schedule will overwrite any
    # duplicate time keys from the common schedule.
    # This is the core of the new logic.
    final_schedule = {**common_schedule, **day_specific_schedule}

    return final_schedule


def parse_time(timestr):
    """Convert 'HH:MM' string to datetime.time object"""
    return datetime.strptime(timestr, "%H:%M").time()


def time_to_str(t):
    """Convert datetime.time to 'HH:MM' string"""
    return t.strftime("%H:%M")


def add_minutes_to_time(timestr, minutes):
    """Add minutes to 'HH:MM' and return new 'HH:MM' string"""
    dt = datetime.strptime(timestr, "%H:%M")
    new_dt = dt + timedelta(minutes=minutes)
    return new_dt.strftime("%H:%M")


def main():
    # Load settings and time blocks
    settings, time_blocks, time_points = load_settings()
    SOUND_FILE = settings.get("sound_file", "/System/Library/Sounds/Ping.aiff")
    ALARM_INTERVAL = settings.get("alarm_interval", 5)
    MAX_ALARM_DURATION = settings.get("max_alarm_duration", 300)

    notified_today = set()

    # store pending end alarms: { end_time_str: message }
    pending_end_alarms = {}

    while True:
        now_str = datetime.now().strftime("%H:%M")
        today_schedule = get_today_schedule()

        # First, process any scheduled start events
        if now_str in today_schedule and now_str not in notified_today:
            event = today_schedule[now_str]

            if isinstance(event, str):
                # string message
                # if event is a time_block, schedule an end alarm
                if event in time_blocks:
                    duration = time_blocks[event]
                    end_time_str = add_minutes_to_time(now_str, duration)
                    start_message = f"{event} ⏱️ ({duration}min)"
                    alarm(
                        "开始",
                        start_message,
                        SOUND_FILE,
                        ALARM_INTERVAL,
                        MAX_ALARM_DURATION,
                    )
                    notified_today.add(now_str)

                    end_message = f"{event} 结束！休息一下 🎉"
                    pending_end_alarms[end_time_str] = end_message

                # if event is a time_point, trigger a simple alarm
                elif event in time_points:
                    message = time_points[event]
                    alarm(
                        "提醒", message, SOUND_FILE, ALARM_INTERVAL, MAX_ALARM_DURATION
                    )
                    notified_today.add(now_str)

                else:
                    print(f"Warning: Unknown event type at {now_str}")
                    continue

            elif isinstance(event, dict) and "block" in event:
                # block-based event
                block_type = event.get("block")
                title = event.get("title", block_type)

                if block_type not in time_blocks:
                    print(f"Warning: Unknown block type '{block_type}' at {now_str}")
                    continue

                duration = time_blocks[block_type]
                end_time_str = add_minutes_to_time(now_str, duration)

                # Trigger START alarm
                start_message = f"{title} ⏱️ ({duration}min)"
                alarm(
                    "开始",
                    start_message,
                    SOUND_FILE,
                    ALARM_INTERVAL,
                    MAX_ALARM_DURATION,
                )
                notified_today.add(now_str)

                # Schedule END alarm
                end_message = f"{title} 结束！休息一下 🎉"
                pending_end_alarms[end_time_str] = end_message

        # process any pending end alarms
        if now_str in pending_end_alarms and now_str not in notified_today:
            message = pending_end_alarms[now_str]
            alarm("结束提醒", message, SOUND_FILE, ALARM_INTERVAL, MAX_ALARM_DURATION)
            notified_today.add(now_str)
            del pending_end_alarms[now_str]  # remove after triggering

        # Reset at midnight
        if now_str == "00:00":
            notified_today.clear()
            pending_end_alarms.clear()

        time.sleep(20)


if __name__ == "__main__":
    main()
