import time
import subprocess
import tomllib
from datetime import datetime
from pathlib import Path


def load_toml_file(filename):
    """Helper to load a single TOML file"""
    script_dir = Path(__file__).parent
    file_path = script_dir / filename

    if not file_path.exists():
        raise FileNotFoundError(f"Configuration file not found: {file_path}")

    with open(file_path, "rb") as f:
        return tomllib.load(f)


def load_settings():
    """Load settings from settings.toml"""
    config = load_toml_file("settings.toml")
    return config.get("settings", {})


def load_week_schedule(config_path):
    """Load week schedule from config_path"""
    return load_toml_file(config_path)


def play_sound(sound_file):
    """Play system sound using afplay"""
    subprocess.Popen(["afplay", sound_file])


def show_dialog(message):
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
        play_sound(sound_file)
        button = show_dialog(message)
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
    """Get today's schedule based on weekday and week parity"""
    now = datetime.now()
    weekday_en = now.strftime("%A").lower()  # e.g., 'monday'

    # Map to lowercase English weekday names expected in TOML
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

    # Load appropriate schedule based on week parity
    parity = get_week_parity()
    if parity == "odd":
        schedule_data = load_week_schedule("odd_weeks.toml")
    else:
        schedule_data = load_week_schedule("even_weeks.toml")

    return schedule_data.get(day_key, {})


def main():
    # Load settings
    settings = load_settings()
    SOUND_FILE = settings.get("sound_file", "/System/Library/Sounds/Ping.aiff")
    ALARM_INTERVAL = settings.get("alarm_interval", 5)
    MAX_ALARM_DURATION = settings.get("max_alarm_duration", 300)

    notified_today = set()

    while True:
        now_str = datetime.now().strftime("%H:%M")
        today_schedule = get_today_schedule()

        # Trigger alarm if time matches and not already notified today
        if now_str in today_schedule and now_str not in notified_today:
            message = today_schedule[now_str]
            alarm(
                "reminder",
                message,
                SOUND_FILE,
                ALARM_INTERVAL,
                MAX_ALARM_DURATION,
            )
            notified_today.add(now_str)

        # Reset notifications at midnight
        if now_str == "00:00":
            notified_today.clear()

        time.sleep(10)  # Check every 10 seconds


if __name__ == "__main__":
    main()