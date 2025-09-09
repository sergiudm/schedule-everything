import time
import subprocess
import tomllib
import os
from datetime import datetime
from pathlib import Path


def load_config():
    """Load configuration from TOML file"""
    script_dir = Path(__file__).parent
    config_path = script_dir / "schedule.toml"

    if not config_path.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")

    with open(config_path, "rb") as f:
        config = tomllib.load(f)

    return config


def play_sound(sound_file):
    """Play system sound using afplay"""
    subprocess.Popen(["afplay", sound_file])


def show_dialog(message):
    """Show AppleScript dialog with 'snooze' button"""
    result = subprocess.run(
        [
            "osascript",
            "-e",
            f'display dialog "{message}" buttons {{"snooze"}} default button "snooze"',
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
        if "snooze" in button:
            break
        if time.time() - start_time > max_alarm_duration:
            break
        time.sleep(alarm_interval)


def get_week_parity():
    """Return 'odd' or 'even' based on ISO calendar week number"""
    week_number = datetime.now().isocalendar().week
    return "odd" if week_number % 2 == 1 else "even"


def get_today_schedule(config):
    """Get today's schedule based on weekday and week parity"""
    now = datetime.now()
    weekday_en = now.strftime("%A").lower()  # e.g., 'monday'
    # Map English weekday to your config's expected keys (assuming lowercase English)
    weekday_map = {
        "monday": "monday",
        "tuesday": "tuesday",
        "wednesday": "wednesday",
        "thursday": "thursday",
        "friday": "friday",
        "saturday": "saturday",
        "sunday": "sunday",
    }
    day_key = weekday_map.get(weekday_en, None)
    if not day_key:
        return {}

    parity = get_week_parity()
    schedule_section = config.get("schedule", {}).get(parity, {}).get(day_key, {})
    return schedule_section


def main():
    # Load configuration
    config = load_config()
    settings = config.get("settings", {})

    # Configuration variables
    SOUND_FILE = settings.get("sound_file", "/System/Library/Sounds/Ping.aiff")
    ALARM_INTERVAL = settings.get("alarm_interval", 5)
    MAX_ALARM_DURATION = settings.get("max_alarm_duration", 300)

    notified_today = set()

    while True:
        now_str = datetime.now().strftime("%H:%M")
        today_schedule = get_today_schedule(config)

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