import tomllib
import time
import subprocess
import platform
from datetime import datetime, timedelta


# system
def get_platform():
    system = platform.system().lower()
    if system == "darwin":
        return "macos"
    elif system == "linux":
        return "linux"
    elif system == "windows":
        return "windows"
    else:
        return "unknown"


# path & config
def load_toml_file(file_path) -> dict[str, str]:
    """Helper to load a single TOML file from config directory"""
    with open(file_path, "rb") as f:
        return tomllib.load(f)


# interation
def play_sound_macos(sound_file):
    """Play system sound using afplay"""
    subprocess.Popen(["afplay", sound_file])


def play_sound_linux(sound_file):
    """Play sound using Linux audio systems"""
    # Try multiple audio backends
    for cmd in [["paplay", sound_file], ["aplay", sound_file], ["play", sound_file]]:
        try:
            subprocess.Popen(cmd, stderr=subprocess.DEVNULL)
            return
        except FileNotFoundError:
            continue
    print(f"Warning: Could not play sound {sound_file}")


def play_sound(sound_file):
    platform_name = get_platform()
    if platform_name == "macos":
        play_sound_macos(sound_file)
    elif platform_name == "linux":
        play_sound_linux(sound_file)
    else:
        print(f"Sound playback not supported on {platform_name}")


def show_dialog_macos(message):
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


def show_dialog_linux(message):
    """Show dialog using Linux desktop notification systems"""
    # Try multiple dialog backends
    for cmd_template in [
        ["zenity", "--info", "--text={}"],
        ["kdialog", "--msgbox", "{}"],
        ["notify-send", "--urgency=critical", "Reminder", "{}"],
    ]:
        try:
            cmd = [arg.format(message) if "{}" in arg else arg for arg in cmd_template]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            return "OK" if result.returncode == 0 else "Cancel"
        except (FileNotFoundError, subprocess.TimeoutExpired):
            continue
    print(f"Warning: Could not show dialog: {message}")
    return "OK"


def show_dialog(message):
    platform_name = get_platform()
    if platform_name == "macos":
        return show_dialog_macos(message)
    elif platform_name == "linux":
        return show_dialog_linux(message)
    else:
        print(f"Dialog display not supported on {platform_name}")
        return "OK"


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
