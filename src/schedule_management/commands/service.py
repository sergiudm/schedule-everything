"""
Service Commands - CLI commands for managing the reminder service.

This module provides CLI command handlers for service management:
- update_command: Update schedule files from git repository
- stop_command: Stop the running reminder-runner service
- report_command: Generate report manually

These commands manage the lifecycle and configuration of the schedule
reminder system.

Example Usage (via CLI):
    $ rmd update          # Pull latest schedule files from git
    $ rmd stop            # Stop the reminder service
    $ rmd report          # Generate manual report
"""

import os
import signal
import subprocess
import sys
from pathlib import Path

from schedule_management import (
    SETTINGS_PATH,
    ODD_PATH,
    EVEN_PATH,
    DDL_PATH,
    HABIT_PATH,
)


# =============================================================================
# UPDATE COMMAND
# =============================================================================


def update_command(args) -> int:
    """
    Handle the 'update' command - update schedule files from remote.

    Performs git pull in the configuration directory to fetch the latest
    schedule, settings, and habit files from the remote repository.

    Args:
        args: Namespace (unused, for CLI compatibility)

    Returns:
        0 on success, 1 on error

    Side Effects:
        - Runs `git pull --rebase` in the config directory
        - May modify local schedule files

    Example:
        $ rmd update
        📥 Updating schedule files...
        Successfully pulled latest changes
    """
    print("📥 Updating schedule files...")

    # Determine config directory from known paths
    config_dir = Path(SETTINGS_PATH).parent

    if not config_dir.exists():
        print(f"❌ Config directory not found: {config_dir}")
        return 1

    # Verify git repository
    git_dir = config_dir / ".git"
    if not git_dir.exists():
        print(f"⚠️  Config directory is not a git repository: {config_dir}")
        print("   Update requires git version control.")
        return 1

    try:
        # Execute git pull with rebase
        result = subprocess.run(
            ["git", "-C", str(config_dir), "pull", "--rebase"],
            capture_output=True,
            text=True,
            check=False,
        )

        if result.returncode == 0:
            print("✅ Successfully pulled latest changes")

            # Show what changed (if anything meaningful)
            if "Already up to date" in result.stdout:
                print("   Already up to date.")
            else:
                print(result.stdout.strip())

            return 0
        else:
            print(f"❌ Git pull failed:")
            print(result.stderr.strip())
            return 1

    except FileNotFoundError:
        print("❌ Git not found. Please install git to use update.")
        return 1
    except Exception as e:
        print(f"❌ Error updating: {e}")
        return 1


# =============================================================================
# STOP COMMAND
# =============================================================================


def stop_command(args) -> int:
    """
    Handle the 'stop' command - stop the running reminder service.

    Finds and terminates the reminder-runner process by sending SIGTERM.
    Uses 'pgrep' to find processes matching 'reminder-runner'.

    Args:
        args: Namespace (unused, for CLI compatibility)

    Returns:
        0 on success, 1 on error

    Side Effects:
        - Sends SIGTERM to reminder-runner process
        - Stops all scheduled notifications until restarted

    Example:
        $ rmd stop
        Stopping reminder service...
        ✅ Reminder service stopped (PID: 12345)
    """
    print("🛑 Stopping reminder service...")

    try:
        # Find reminder-runner process
        result = subprocess.run(
            ["pgrep", "-f", "reminder-runner"],
            capture_output=True,
            text=True,
            check=False,
        )

        if result.returncode != 0 or not result.stdout.strip():
            print("⚠️  No running reminder-runner process found.")
            return 0  # Not an error - service may not be running

        # Get all matching PIDs
        pids = result.stdout.strip().split("\n")
        current_pid = os.getpid()

        stopped_count = 0
        for pid_str in pids:
            try:
                pid = int(pid_str.strip())

                # Don't kill ourselves if somehow matched
                if pid == current_pid:
                    continue

                os.kill(pid, signal.SIGTERM)
                print(f"✅ Stopped reminder-runner (PID: {pid})")
                stopped_count += 1

            except (ValueError, ProcessLookupError, PermissionError) as e:
                print(f"⚠️  Could not stop PID {pid_str}: {e}")

        if stopped_count == 0:
            print("⚠️  No reminder-runner processes were stopped.")
        else:
            print(f"   Total processes stopped: {stopped_count}")

        return 0

    except FileNotFoundError:
        print("❌ 'pgrep' command not found.")
        print(
            "   Try finding the process manually with 'ps aux | grep reminder-runner'"
        )
        return 1
    except Exception as e:
        print(f"❌ Error stopping service: {e}")
        return 1


# =============================================================================
# REPORT COMMAND
# =============================================================================


def report_command(args) -> int:
    """
    Handle the 'report' command - generate a manual report.

    Creates a report for the specified date range using the ReportGenerator.
    Reports include habit completion rates, task statistics, and productivity
    metrics.

    Args:
        args: Namespace with optional 'date' and 'days' parameters
            - date: Target date for report (default: today)
            - days: Number of days to include (default: 7)

    Returns:
        0 on success, 1 on error

    Side Effects:
        - Creates report file in reports directory
        - May open generated report in browser

    Example:
        $ rmd report                 # Last 7 days
        $ rmd report -d 2024-01-15   # Week ending on specific date
        $ rmd report --days 30       # Last 30 days
    """
    print("📊 Generating report...")

    try:
        # Import here to avoid circular dependency
        from schedule_management.report import ReportGenerator
        from datetime import datetime, timedelta

        # Parse target date
        if hasattr(args, "date") and args.date:
            try:
                target_date = datetime.strptime(args.date, "%Y-%m-%d").date()
            except ValueError:
                print(f"❌ Invalid date format: {args.date}")
                print("   Use YYYY-MM-DD format (e.g., 2024-01-15)")
                return 1
        else:
            target_date = datetime.now().date()

        # Parse number of days
        days = getattr(args, "days", 7) or 7

        # Calculate date range
        start_date = target_date - timedelta(days=days - 1)
        end_date = target_date

        print(f"   Date range: {start_date} to {end_date}")
        print(f"   Days included: {days}")

        # Generate report
        generator = ReportGenerator()
        report_path = generator.generate_report(
            start_date=start_date,
            end_date=end_date,
        )

        if report_path:
            print(f"\n✅ Report generated: {report_path}")

            # Try to open on macOS
            if sys.platform == "darwin":
                try:
                    subprocess.run(["open", str(report_path)], check=False)
                except Exception:
                    pass  # Silent fail for opening

            return 0
        else:
            print("⚠️  Report generation completed but no file was created.")
            return 1

    except ImportError as e:
        print(f"❌ Missing dependency for report generation: {e}")
        return 1
    except Exception as e:
        print(f"❌ Error generating report: {e}")
        return 1


# =============================================================================
# SCHEDULE EDIT COMMAND (OPTIONAL)
# =============================================================================


def edit_schedule_command(args) -> int:
    """
    Handle the 'edit' command - open schedule files in editor.

    Opens the appropriate schedule file (settings, odd, even) in the
    system's default editor or $EDITOR.

    Args:
        args: Namespace with 'file' parameter
            - file: Which file to edit ('settings', 'odd', 'even', 'habits')

    Returns:
        0 on success, 1 on error

    Example:
        $ rmd edit settings    # Edit settings.toml
        $ rmd edit odd         # Edit odd week schedule
    """
    file_map = {
        "settings": SETTINGS_PATH,
        "odd": ODD_PATH,
        "even": EVEN_PATH,
        "deadlines": DDL_PATH,
        "ddl": DDL_PATH,
        "habits": HABIT_PATH,
    }

    target = getattr(args, "file", "settings").lower()

    if target not in file_map:
        print(f"❌ Unknown file: {target}")
        print(f"   Available: {', '.join(file_map.keys())}")
        return 1

    file_path = file_map[target]

    if not Path(file_path).exists():
        print(f"⚠️  File does not exist: {file_path}")
        print("   Creating empty file...")
        Path(file_path).touch()

    # Find editor
    editor = os.environ.get("EDITOR", os.environ.get("VISUAL"))

    if not editor:
        # Try common editors
        for candidate in ["code", "vim", "nano", "vi"]:
            try:
                subprocess.run(["which", candidate], capture_output=True, check=True)
                editor = candidate
                break
            except subprocess.CalledProcessError:
                continue

    if not editor:
        print(f"❌ No editor found. Set $EDITOR environment variable.")
        print(f"   File path: {file_path}")
        return 1

    print(f"📝 Opening {target} in {editor}...")

    try:
        subprocess.run([editor, str(file_path)], check=False)
        return 0
    except Exception as e:
        print(f"❌ Could not open editor: {e}")
        return 1
