import tomllib
from typing import Dict, Tuple
import time
import subprocess
from datetime import datetime, timedelta


# path & config
def load_toml_file(file_path) -> Dict:
    """Helper to load a single TOML file from config directory"""
    with open(file_path, "rb") as f:
        return tomllib.load(f)

# interation
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


# timing & time format
def get_week_parity():
    """Return 'odd' or 'even' based on ISO calendar week number"""
    week_number = datetime.now().isocalendar().week
    return "odd" if week_number % 2 == 1 else "even"


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
