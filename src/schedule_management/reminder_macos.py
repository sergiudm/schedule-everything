import time
import os
import subprocess
import tomllib
from datetime import datetime, timedelta
from pathlib import Path
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from collections import defaultdict


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


def should_skip_today(settings):
    """Check if today should be skipped based on skip_days setting"""
    skip_days = settings.get("skip_days", [])
    if not skip_days:
        return False
    
    current_weekday = datetime.now().strftime("%A").lower()
    return current_weekday in skip_days


def get_today_schedule():
    """
    Get today's schedule by merging the day-specific schedule over the common schedule.
    Returns empty dict if today should be skipped based on skip_days setting.
    """
    # Load settings to check if today should be skipped
    settings, _, _ = load_settings()
    
    # Check if today should be skipped
    if should_skip_today(settings):
        return {}

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


def visualize_schedule():
    """
    Create visual schedule charts for both odd and even weeks.
    Generates two PNG files: 'odd_week_schedule.png' and 'even_week_schedule.png'
    """
    # Load settings and schedules
    settings, time_blocks, time_points = load_settings()
    odd_schedule = load_odd_week_schedule()
    even_schedule = load_even_week_schedule()

    # Color mapping for different activity types
    colors = {
        "pomodoro": "#FF6B6B",  # Red
        "long_break": "#4ECDC4",  # Teal
        "napping": "#45B7D1",  # Blue
        "meeting": "#96CEB4",  # Green
        "exercise": "#FFEAA7",  # Yellow
        "lunch": "#DDA0DD",  # Plum
        "summary_time": "#FFB347",  # Orange
        "go_to_bed": "#9370DB",  # Medium Purple
        "other": "#D3D3D3",  # Light Gray
    }

    days_order = [
        "monday",
        "tuesday",
        "wednesday",
        "thursday",
        "friday",
        "saturday",
        "sunday",
    ]

    def create_schedule_chart(schedule_data, title, filename):
        fig, ax = plt.subplots(figsize=(16, 10))

        schedule_by_day = defaultdict(list)

        # Process each day
        for day_idx, day in enumerate(days_order):
            day_schedule = {}

            # Merge common schedule with day-specific schedule
            if "common" in schedule_data:
                day_schedule.update(schedule_data["common"])
            if day in schedule_data:
                day_schedule.update(schedule_data[day])

            # Convert schedule to visual elements
            for time_str, activity in day_schedule.items():
                time_parts = time_str.split(":")
                hour = int(time_parts[0])
                minute = int(time_parts[1])
                time_decimal = hour + minute / 60.0

                # Handle both string activities and dict-based activities
                if isinstance(activity, str):
                    activity_name = activity
                elif isinstance(activity, dict) and "block" in activity:
                    activity_name = activity.get("title", activity["block"])
                else:
                    activity_name = str(activity)

                # Determine duration and end time
                if activity_name in time_blocks:
                    duration_minutes = time_blocks[activity_name]
                    duration_hours = duration_minutes / 60.0
                    end_time = time_decimal + duration_hours
                elif activity_name in time_points:
                    # Point events get a small visual marker
                    duration_hours = 0.1
                    end_time = time_decimal + duration_hours
                else:
                    # Default duration for unknown activities
                    duration_hours = 0.1
                    end_time = time_decimal + duration_hours

                color = colors.get(activity_name, colors["other"])

                # Create rectangle for the time block
                rect = patches.Rectangle(
                    (day_idx, time_decimal),
                    0.8,  # width
                    duration_hours,  # height
                    linewidth=1,
                    edgecolor="black",
                    facecolor=color,
                    alpha=0.7,
                )
                ax.add_patch(rect)

                # Add text label
                text_x = day_idx + 0.4
                text_y = time_decimal + duration_hours / 2

                # Format the label
                if activity_name in time_blocks:
                    label = f"{activity_name}\n{time_str}\n({duration_minutes}min)"
                else:
                    label = f"{activity_name}\n{time_str}"

                ax.text(
                    text_x,
                    text_y,
                    label,
                    ha="center",
                    va="center",
                    fontsize=8,
                    weight="bold",
                    bbox=dict(boxstyle="round,pad=0.2", facecolor="white", alpha=0.8),
                )

        # Customize the chart
        ax.set_xlim(-0.5, len(days_order) - 0.5)
        ax.set_ylim(24, 6)  # Inverted to show morning at top

        # Set up axes
        ax.set_xticks(range(len(days_order)))
        ax.set_xticklabels([day.capitalize() for day in days_order])

        # Set up time axis (hours)
        hour_ticks = list(range(6, 25))
        ax.set_yticks(hour_ticks)
        ax.set_yticklabels([f"{h:02d}:00" for h in hour_ticks])

        # Add grid
        ax.grid(True, alpha=0.3)

        # Add title and labels
        ax.set_title(title, fontsize=16, weight="bold", pad=20)
        ax.set_xlabel("Days of the Week", fontsize=12, weight="bold")
        ax.set_ylabel("Time of Day", fontsize=12, weight="bold")

        # Create legend
        legend_elements = []
        used_activities = set()

        # Collect all activities used in the schedule
        for day in days_order:
            day_schedule = {}
            if "common" in schedule_data:
                day_schedule.update(schedule_data["common"])
            if day in schedule_data:
                day_schedule.update(schedule_data[day])

            for activity in day_schedule.values():
                if isinstance(activity, str):
                    used_activities.add(activity)
                elif isinstance(activity, dict) and "block" in activity:
                    used_activities.add(activity.get("title", activity["block"]))

        # Create legend patches
        for activity in sorted(used_activities):
            color = colors.get(activity, colors["other"])
            legend_elements.append(patches.Patch(color=color, label=activity))

        ax.legend(handles=legend_elements, loc="center left", bbox_to_anchor=(1, 0.5))

        os.makedirs("schedule_visualization", exist_ok=True)
        # Adjust layout and save
        plt.tight_layout()
        plt.savefig(filename, dpi=300, bbox_inches="tight")
        plt.close()

        print(f"Schedule visualization saved as '{filename}'")

    # Generate both charts
    create_schedule_chart(
        odd_schedule,
        "Odd Week Schedule",
        "schedule_visualization/odd_week_schedule.png",
    )
    create_schedule_chart(
        even_schedule,
        "Even Week Schedule",
        "schedule_visualization/even_week_schedule.png",
    )

    print("\nSchedule visualization complete!")
    print("Generated files:")
    print("- odd_week_schedule.png")
    print("- even_week_schedule.png")


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

        # Skip processing if today is a skipped day (empty schedule)
        if not today_schedule:
            time.sleep(20)
            continue

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
    import sys

    # Check if user wants to generate visualizations
    if len(sys.argv) > 1 and sys.argv[1] == "--view":
        visualize_schedule()
    else:
        main()
