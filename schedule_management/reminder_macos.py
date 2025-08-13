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


# Load configuration
config = load_config()
settings = config.get("settings", {})
schedule = config.get("schedule", {})

# Configuration variables
SOUND_FILE = settings.get("sound_file", "/System/Library/Sounds/Ping.aiff")
ALARM_INTERVAL = settings.get("alarm_interval", 30)
MAX_ALARM_DURATION = settings.get("max_alarm_duration", 300)


def play_sound():
    subprocess.Popen(["afplay", SOUND_FILE])


def show_dialog(message):
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


def alarm(title, message):
    start_time = time.time()
    while True:
        play_sound()
        button = show_dialog(message)
        if "停止闹铃" in button:
            break
        if time.time() - start_time > MAX_ALARM_DURATION:
            break
        time.sleep(ALARM_INTERVAL)


notified_today = set()

while True:
    now = datetime.now().strftime("%H:%M")
    if now in schedule and now not in notified_today:
        alarm("作息提醒", schedule[now])
        notified_today.add(now)

    if now == "00:00":
        notified_today.clear()

    time.sleep(10)
