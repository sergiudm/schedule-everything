import tomllib
import time
import subprocess
import platform
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

try:
    import matplotlib.pyplot as plt
    import matplotlib.patches as patches
    from matplotlib.backends.backend_pdf import PdfPages

    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False


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


def _escape_applescript_string(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ")


def choose_multiple(options: list[str], title: str, prompt: str) -> list[str] | None:
    """Prompt the user with a GUI multi-select list.

    Returns:
        - list[str]: selected option strings (may be empty if user selects none)
        - None: user cancelled OR no supported GUI backend is available
    """
    platform_name = get_platform()

    if platform_name == "macos":
        escaped_items = ",".join(
            f'"{_escape_applescript_string(item)}"' for item in options
        )
        script = f"""
set optionsList to {{{escaped_items}}}
set promptText to "{_escape_applescript_string(prompt)}"
set titleText to "{_escape_applescript_string(title)}"
set choice to choose from list optionsList with title titleText with prompt promptText with multiple selections allowed
if choice is false then
  return "__CANCEL__"
end if
set AppleScript's text item delimiters to "\\n"
return choice as text
""".strip()
        try:
            result = subprocess.run(
                ["osascript", "-e", script],
                capture_output=True,
                text=True,
                timeout=120,
            )
        except FileNotFoundError:
            print("Warning: osascript not found; cannot show habit prompt window.")
            return None
        except subprocess.TimeoutExpired:
            print("Warning: habit prompt window timed out.")
            return None

        if result.returncode != 0:
            return None
        stdout = (result.stdout or "").strip()
        if stdout == "__CANCEL__":
            return None
        if not stdout:
            return []
        return [line for line in stdout.splitlines() if line.strip()]

    if platform_name == "linux":
        # Prefer zenity checklist if available
        zenity_cmd = ["zenity", "--list", "--checklist", "--title", title, "--text", prompt]
        zenity_cmd += ["--column", "Done", "--column", "Habit"]
        for option in options:
            zenity_cmd += ["FALSE", option]
        try:
            result = subprocess.run(
                zenity_cmd + ["--separator", "\n"],
                capture_output=True,
                text=True,
                timeout=120,
            )
            if result.returncode != 0:
                return None
            stdout = (result.stdout or "").strip()
            if not stdout:
                return []
            return [line for line in stdout.splitlines() if line.strip()]
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return None

    return None


def ask_yes_no_macos(question: str, title: str) -> bool | None:
    """
    Show a Yes/No dialog on macOS using AppleScript.
    Returns: True (Yes), False (No), or None (Stop/Cancel).
    """
    script = f"""
set questionText to "{_escape_applescript_string(question)}"
set titleText to "{_escape_applescript_string(title)}"
display dialog questionText with title titleText buttons {{"Stop", "No", "Yes"}} default button "Yes" cancel button "Stop" with icon note
"""
    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            timeout=60,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None

    # Check return code. "Stop" (cancel button) causes non-zero exit code in osascript
    if result.returncode != 0:
        return None

    stdout = result.stdout.strip()
    if "button returned:Yes" in stdout:
        return True
    elif "button returned:No" in stdout:
        return False

    return None


def ask_yes_no(question: str, title: str = "Confirmation") -> bool | None:
    """
    Ask a Yes/No question with a platform-specific dialog.
    Returns: True, False, or None (cancelled/stopped).
    """
    platform_name = get_platform()
    if platform_name == "macos":
        return ask_yes_no_macos(question, title)

    # Simple CLI fallback
    print(f"\n{title}: {question}")
    while True:
        choice = input(" (y/n/s[top]): ").lower().strip()
        if choice.startswith("y"):
            return True
        if choice.startswith("n"):
            return False
        if choice.startswith("s"):
            return None


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


# --- VISUALIZER CLASS ---


class ScheduleVisualizer:
    """
    Handles the generation of beautiful PDF schedules using Matplotlib.
    """

    # Modern, vibrant pastel palette
    COLORS = {
        "pomodoro": "#FF6B6B",  # Soft Red
        "potato": "#EE5253",  # Deeper Red/Pink
        "long_break": "#1DD1A1",  # Bright Teal
        "short_break": "#48DBFB",  # Light Blue
        "napping": "#54A0FF",  # Blue
        "meeting": "#FF9F43",  # Orange
        "exercise": "#Feca57",  # Yellow
        "lunch": "#5F27CD",  # Deep Purple
        "summary_time": "#C8D6E5",  # Light Grey
        "go_to_bed": "#576574",  # Dark Grey
        "other": "#8395A7",  # Blue Grey
        "deep_work": "#0ABDE3",  # Cyan
    }

    # Text color for contrast (White for dark blocks, Dark Grey for light blocks)
    TEXT_COLORS = {
        "exercise": "#333333",  # Yellow needs dark text
        "summary_time": "#333333",
        "default": "#FFFFFF",
    }

    # Explicit durations in minutes for known activity types
    # This fixes the "thin line" issue for potato/pomodoro
    DEFAULT_DURATIONS = {
        "potato": 50,
        "pomodoro": 25,
        "long_break": 15,
        "short_break": 5,
        "lunch": 60,
        "napping": 20,
    }

    DAYS_ORDER = [
        "monday",
        "tuesday",
        "wednesday",
        "thursday",
        "friday",
        "saturday",
        "sunday",
    ]

    def __init__(self, config, odd_schedule: dict, even_schedule: dict):
        self.config = config
        self.odd_schedule = odd_schedule
        self.even_schedule = even_schedule

    def _extract_activity_name(self, activity: Any) -> str:
        if isinstance(activity, str):
            return activity
        elif isinstance(activity, dict) and "block" in activity:
            return activity.get("title", activity["block"])
        else:
            return str(activity)

    def _get_activity_duration(self, activity_name: str) -> float:
        """
        Returns duration in HOURS.
        Checks config first, then manual defaults, then generic fallback.
        """
        # 1. Check Config
        if activity_name in self.config.time_blocks:
            return self.config.time_blocks[activity_name] / 60.0

        # 2. Check Manual Defaults (Case insensitive partial match)
        lower_name = activity_name.lower()
        for key, minutes in self.DEFAULT_DURATIONS.items():
            if key in lower_name:
                return minutes / 60.0

        # 3. Generic Fallback (0.5 hours = 30 mins) ensures visibility
        return 0.5

    def _get_color(self, activity_name: str) -> str:
        """Finds the best matching color."""
        lower_name = activity_name.lower()
        for key, color in self.COLORS.items():
            if key in lower_name:
                return color
        return self.COLORS["other"]

    def _get_text_color(self, activity_name: str) -> str:
        """Finds best text color based on background."""
        lower_name = activity_name.lower()
        for key, color in self.TEXT_COLORS.items():
            if key in lower_name:
                return color
        return self.TEXT_COLORS["default"]

    def _create_chart(self, ax, schedule_data: dict, title: str):
        if not MATPLOTLIB_AVAILABLE:
            return

        # Setup aesthetics
        ax.set_facecolor("#FFFFFF")  # Pure white background for clean look
        used_activities = set()

        # Draw Day Columns background (Alternating subtle grey)
        for i in range(0, len(self.DAYS_ORDER), 2):
            ax.axvspan(i - 0.5, i + 0.5, color="#F7F9FA", zorder=0)

        for day_idx, day in enumerate(self.DAYS_ORDER):
            day_schedule = {}
            if "common" in schedule_data:
                day_schedule.update(schedule_data["common"])
            if day in schedule_data:
                day_schedule.update(schedule_data[day])

            for time_str, activity in day_schedule.items():
                activity_name = self._extract_activity_name(activity)
                used_activities.add(activity_name)

                # Parse time
                time_parts = time_str.split(":")
                hour = int(time_parts[0])
                minute = int(time_parts[1])
                time_decimal = hour + minute / 60.0

                # Calculate duration
                duration_hours = self._get_activity_duration(activity_name)

                # Get Colors
                bg_color = self._get_color(activity_name)
                txt_color = self._get_text_color(activity_name)

                # Draw Block
                rect_width = 0.85  # Slightly thinner for elegance
                rect_x = day_idx - (rect_width / 2)

                # Main colored block
                rect = patches.Rectangle(
                    (rect_x, time_decimal),
                    rect_width,
                    duration_hours,
                    linewidth=0,
                    facecolor=bg_color,
                    alpha=0.9,
                    zorder=2,
                )
                ax.add_patch(rect)

                # Optional: Left accent border for "depth"
                rect_accent = patches.Rectangle(
                    (rect_x, time_decimal),
                    0.04,  # Thin strip on left
                    duration_hours,
                    linewidth=0,
                    facecolor="black",
                    alpha=0.1,
                    zorder=3,
                )
                ax.add_patch(rect_accent)

                # ADD TEXT LABEL inside the block if it's big enough
                if duration_hours >= 0.3:  # Only if block > 18 mins
                    font_size = 8 if duration_hours > 0.5 else 6
                    # Clean up name for display (remove underscores)
                    display_name = activity_name.replace("_", " ").title()

                    # If it's very short, just show first letter or short code
                    if duration_hours < 0.4:
                        display_name = display_name[:3]

                    ax.text(
                        day_idx,
                        time_decimal + (duration_hours / 2),
                        display_name,
                        ha="center",
                        va="center",
                        color=txt_color,
                        fontsize=font_size,
                        fontweight="bold",
                        zorder=4,
                    )

        # Configure Axes
        ax.set_xlim(-0.5, len(self.DAYS_ORDER) - 0.5)
        ax.set_ylim(24, 6)  # 6 AM at top, Midnight at bottom

        # Top X Axis (Days)
        ax.set_xticks(range(len(self.DAYS_ORDER)))
        ax.set_xticklabels(
            [d.upper()[:3] for d in self.DAYS_ORDER],  # MON, TUE...
            fontsize=11,
            weight="bold",
            color="#57606f",
        )
        ax.tick_params(axis="x", pad=10)  # Move labels up slightly

        # Left Y Axis (Time)
        hour_ticks = list(range(6, 25))
        ax.set_yticks(hour_ticks)
        ax.set_yticklabels(
            [f"{h:02d}:00" for h in hour_ticks],
            fontsize=9,
            color="#a4b0be",
            family="monospace",
        )

        # Grid
        ax.grid(True, axis="y", linestyle=":", alpha=0.4, color="#dfe4ea", zorder=1)
        ax.grid(False, axis="x")

        # Clean Spines
        for spine in ax.spines.values():
            spine.set_visible(False)

        # Add a subtle left spine for time anchor
        ax.axvline(-0.5, color="#dfe4ea", linewidth=1)

        # Title
        ax.set_title(
            title.upper(),
            fontsize=20,
            weight="heavy",
            pad=25,
            color="#2f3542",
            loc="left",
        )

        # Legend (only if we have untagged items or want summary)
        # Since we have inline labels, we can make the legend smaller or cleaner
        legend_elements = [
            patches.Patch(
                facecolor=self._get_color(act),
                label=act.replace("_", " ").title(),
                edgecolor="none",
            )
            for act in sorted(used_activities)
        ]

        if legend_elements:
            ax.legend(
                handles=legend_elements,
                loc="upper center",
                bbox_to_anchor=(0.5, -0.08),  # Below chart
                ncol=min(len(used_activities), 6),
                frameon=False,
                fontsize=8,
            )

    def _calculate_weekly_stats(self, schedule_data: dict) -> dict[str, Any]:
        pomodoro_count = 0
        potato_count = 0
        work_hours = 0.0

        work_activities = {"pomodoro", "potato", "deep_work", "meeting"}

        for day in self.DAYS_ORDER:
            day_schedule = {}
            if "common" in schedule_data:
                day_schedule.update(schedule_data["common"])
            if day in schedule_data:
                day_schedule.update(schedule_data[day])

            for _, activity in day_schedule.items():
                activity_name = self._extract_activity_name(activity)

                # Use the unified duration logic
                duration_hours = self._get_activity_duration(activity_name)

                if "pomodoro" in activity_name.lower():
                    pomodoro_count += 1
                if "potato" in activity_name.lower():
                    potato_count += 1

                # Check if it's a work activity
                if (
                    activity_name in work_activities
                    or "pomodoro" in activity_name.lower()
                    or "potato" in activity_name.lower()
                ):
                    work_hours += duration_hours

        return {
            "pomodoro_count": pomodoro_count,
            "work_hours": work_hours,
            "potato_count": potato_count,
        }

    def _create_stats_page(self, ax, odd_stats: dict, even_stats: dict):
        ax.axis("off")
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)

        # Decorative background circle
        circle = patches.Circle((0.5, 0.5), 0.4, color="#F7F9FA", zorder=0)
        ax.add_patch(circle)

        # Title
        ax.text(
            0.5,
            0.92,
            "WEEKLY STATISTICS",
            ha="center",
            va="center",
            fontsize=22,
            weight="bold",
            color="#2f3542",
        )
        ax.plot([0.3, 0.7], [0.89, 0.89], color="#ff6b6b", linewidth=2)  # Underline

        def draw_stat_column(x_pos, title, stats, color_theme):
            # Header
            ax.text(
                x_pos,
                0.78,
                title,
                ha="center",
                fontsize=16,
                weight="bold",
                color=color_theme,
            )

            # Stat 1: Work Hours
            ax.text(
                x_pos,
                0.65,
                f"{stats['work_hours']:.1f}h",
                ha="center",
                fontsize=45,
                weight="heavy",
                color="#2f3542",
            )
            ax.text(
                x_pos,
                0.58,
                "Work Time",
                ha="center",
                fontsize=12,
                color="#a4b0be",
                weight="medium",
            )

            # Stat 2: Pomodoros
            ax.text(
                x_pos,
                0.45,
                f"{stats['pomodoro_count']}",
                ha="center",
                fontsize=45,
                weight="heavy",
                color="#2f3542",
            )
            ax.text(
                x_pos,
                0.38,
                "Pomodoros",
                ha="center",
                fontsize=12,
                color="#a4b0be",
                weight="medium",
            )

            # Stat 3: Potatoes
            ax.text(
                x_pos,
                0.25,
                f"{stats['potato_count']}",
                ha="center",
                fontsize=45,
                weight="heavy",
                color="#2f3542",
            )
            ax.text(
                x_pos,
                0.18,
                "Potatoes",
                ha="center",
                fontsize=12,
                color="#a4b0be",
                weight="medium",
            )

        draw_stat_column(0.25, "ODD WEEK", odd_stats, "#ff6b6b")
        draw_stat_column(0.75, "EVEN WEEK", even_stats, "#54a0ff")

        # Vertical Divider
        ax.plot([0.5, 0.5], [0.15, 0.8], color="#dfe4ea", linewidth=1, linestyle="--")

    def visualize(self):
        if not MATPLOTLIB_AVAILABLE:
            print(
                "❌ matplotlib is not available. Please install it: pip install matplotlib"
            )
            return

        import platform

        if platform.system() == "Windows":
            desktop_path = Path.home() / "Desktop"
        else:
            desktop_path = Path.home() / "Desktop"

        pdf_filename = desktop_path / "schedule_visualization.pdf"

        # Global font settings for cleaner look
        plt.rcParams["font.family"] = "sans-serif"
        plt.rcParams["font.sans-serif"] = ["Arial", "Helvetica", "DejaVu Sans"]

        with PdfPages(pdf_filename) as pdf:
            # Page 1: Odd Week
            fig1, ax1 = plt.subplots(figsize=(14, 9))  # 14x9 is a good landscape aspect
            self._create_chart(ax1, self.odd_schedule, "Odd Week Schedule")
            plt.tight_layout()
            pdf.savefig(fig1, dpi=300, bbox_inches="tight")
            plt.close(fig1)

            # Page 2: Even Week
            fig2, ax2 = plt.subplots(figsize=(14, 9))
            self._create_chart(ax2, self.even_schedule, "Even Week Schedule")
            plt.tight_layout()
            pdf.savefig(fig2, dpi=300, bbox_inches="tight")
            plt.close(fig2)

            # Page 3: Stats
            fig3 = plt.figure(figsize=(14, 9))
            ax3 = fig3.add_subplot(111)
            odd_stats = self._calculate_weekly_stats(self.odd_schedule)
            even_stats = self._calculate_weekly_stats(self.even_schedule)
            self._create_stats_page(ax3, odd_stats, even_stats)
            plt.tight_layout()
            pdf.savefig(fig3, dpi=300, bbox_inches="tight")
            plt.close(fig3)

        print(f"Schedule visualization saved as '{pdf_filename}'")
        print("\nSchedule visualization complete!")
        print("Generated file:")
        print("- schedule_visualization.pdf (on Desktop)")
        print("  - Page 1: Odd Week Schedule")
        print("  - Page 2: Even Week Schedule")
        print("  - Page 3: Statistics")
