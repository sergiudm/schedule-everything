"""
Service Commands - CLI commands for managing the reminder service.

This module provides CLI command handlers for service management:
- update_command: Reload schedule files and restart the reminder service
- switch_command: Switch the active versioned config snapshot and reload
- stop_command: Stop the running reminder-runner service
- report_command: Generate report manually

These commands manage the lifecycle and configuration of the schedule
reminder system.

Example Usage (via CLI):
    $ rmd update          # Reload local config, pulling from git when present
    $ rmd switch 2        # Activate user_config_2 and reload the service
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
from schedule_management.i18n import _t
from schedule_management.config_layout import (
    list_config_ids,
    preview_active_config_dir,
    resolve_config_root_dir,
    write_active_config_id,
)


# =============================================================================
# UPDATE HELPERS
# =============================================================================


def _resolve_config_dir() -> Path:
    """Resolve the root config directory from the runtime environment."""
    return resolve_config_root_dir()


def _has_git_metadata(config_dir: Path) -> bool:
    """Return whether the config directory is backed by a local git checkout."""
    return (config_dir / ".git").exists()


def _find_installer_script(script_name: str) -> Path | None:
    """Search near the active Python executable for installer helper scripts."""
    search_roots: list[Path] = []

    for raw_path in (sys.executable, sys.argv[0]):
        if not raw_path:
            continue

        resolved = Path(raw_path).expanduser()
        try:
            resolved = resolved.resolve()
        except OSError:
            resolved = resolved.absolute()

        search_roots.append(resolved)
        search_roots.extend(resolved.parents)

    seen: set[Path] = set()
    for root in search_roots:
        candidate = root / script_name
        if candidate in seen:
            continue

        seen.add(candidate)
        if candidate.is_file():
            return candidate

    return None


def _restart_reminder_service() -> tuple[bool, str]:
    """Restart the installer-managed reminder service when helper scripts exist."""
    restart_script = _find_installer_script("restart_reminders.sh")
    if restart_script is None:
        return False, "No installer restart script found."

    try:
        result = subprocess.run(
            [str(restart_script)],
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError as exc:
        return False, str(exc)

    if result.returncode == 0:
        return True, ""

    details = result.stderr.strip() or result.stdout.strip()
    if not details:
        details = f"Restart script exited with status {result.returncode}."
    return False, details


# =============================================================================
# UPDATE COMMAND
# =============================================================================


def update_command(args) -> int:
    """
    Handle the 'update' command - reload schedule files and service state.

    If the config directory is git-managed, this command performs a
    `git pull --rebase` before attempting to restart the installer-managed
    reminder service. For local-only config directories, it skips the git
    step and just reloads the service when the restart script is available.

    Args:
        args: Namespace (unused, for CLI compatibility)

    Returns:
        0 on success, 1 on error

    Side Effects:
        - May run `git pull --rebase` in the config directory
        - May restart the reminder service via `restart_reminders.sh`

    Example:
        $ rmd update
        📥 Updating schedule files...
        Successfully pulled latest changes
    """
    print(_t("📥 Updating schedule files..."))

    config_dir = _resolve_config_dir()

    if not config_dir.exists():
        print(_t("❌ Config directory not found: {config_dir}").format(config_dir=config_dir))
        return 1

    try:
        if _has_git_metadata(config_dir):
            try:
                result = subprocess.run(
                    ["git", "-C", str(config_dir), "pull", "--rebase"],
                    capture_output=True,
                    text=True,
                    check=False,
                )
            except FileNotFoundError:
                print(_t("❌ Git not found. Please install git to use update."))
                return 1

            if result.returncode == 0:
                print(_t("✅ Successfully pulled latest changes"))

                if "Already up to date" in result.stdout:
                    print(_t("   Already up to date."))
                else:
                    print(result.stdout.strip())
            else:
                print(_t("❌ Git pull failed:"))
                print(result.stderr.strip())
                return 1
        else:
            print(_t("ℹ️  Config directory is not a git repository: {config_dir}").format(config_dir=config_dir))
            print(_t("   Skipping git pull and using local schedule files as-is."))

        restarted, details = _restart_reminder_service()
        if restarted:
            print(_t("✅ Reminder service restarted"))
        elif details == "No installer restart script found.":
            print(_t("ℹ️  No installer restart script found."))
            print(_t("   Restart the reminder service manually if it is already running."))
        else:
            print(_t("❌ Reminder service restart failed:"))
            print(details)
            return 1

        print(_t("✅ Update finished"))
        return 0

    except Exception as e:
        print(_t("❌ Error updating: {e}").format(e=e))
        return 1


def switch_command(args) -> int:
    """
    Handle the 'switch' command - activate a different versioned config set.

    This updates the active config marker under the root config directory and
    then reloads the reminder service so the running runner process picks up
    the newly selected config set.
    """
    config_root_dir = _resolve_config_dir()
    available_ids = list_config_ids(config_root_dir)
    if not available_ids:
        print(_t("❌ No config sets found under: {config_root_dir}").format(config_root_dir=config_root_dir))
        print(_t("   Create or migrate a schedule first so user_config_0 exists."))
        return 1

    raw_config_id = str(getattr(args, "config_id", "")).strip()
    try:
        requested_id = int(raw_config_id)
    except ValueError:
        print(_t("❌ Invalid config id: {config_id}").format(config_id=raw_config_id or "(empty)"))
        print(_t("   Valid config ids: {ids}").format(ids=', '.join(str(item) for item in available_ids)))
        return 1

    if requested_id not in available_ids:
        print(_t("❌ Invalid config id: {config_id}").format(config_id=requested_id))
        print(_t("   Valid config ids: {ids}").format(ids=', '.join(str(item) for item in available_ids)))
        return 1

    write_active_config_id(config_root_dir, requested_id)
    active_config_dir = preview_active_config_dir(config_root_dir)
    print(_t("✅ Switched to user_config_{requested_id}").format(requested_id=requested_id))
    print(_t("   Active config directory: {directory}").format(directory=active_config_dir))

    restarted, details = _restart_reminder_service()
    if restarted:
        print(_t("✅ Reminder service restarted"))
        return 0

    if details == "No installer restart script found.":
        print(_t("ℹ️  No installer restart script found."))
        print(_t("   Restart the reminder service manually if it is already running."))
        return 0

    print(_t("❌ Reminder service restart failed:"))
    print(details)
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
    print(_t("🛑 Stopping reminder service..."))

    try:
        # Find reminder-runner process
        result = subprocess.run(
            ["pgrep", "-f", "reminder-runner"],
            capture_output=True,
            text=True,
            check=False,
        )

        if result.returncode != 0 or not result.stdout.strip():
            print(_t("⚠️  No running reminder-runner process found."))
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
                print(_t("✅ Stopped reminder-runner (PID: {pid})").format(pid=pid))
                stopped_count += 1

            except (ValueError, ProcessLookupError, PermissionError) as e:
                print(_t("⚠️  Could not stop PID {pid}: {e}").format(pid=pid_str, e=e))

        if stopped_count == 0:
            print(_t("⚠️  No reminder-runner processes were stopped."))
        else:
            print(_t("   Total processes stopped: {count}").format(count=stopped_count))

        return 0

    except FileNotFoundError:
        print(_t("❌ 'pgrep' command not found."))
        print(
            _t("   Try finding the process manually with 'ps aux | grep reminder-runner'")
        )
        return 1
    except Exception as e:
        print(_t("❌ Error stopping service: {e}").format(e=e))
        return 1


# =============================================================================
# REPORT COMMAND
# =============================================================================


def report_command(args) -> int:
    """
    Handle the 'report' command - generate a manual report.

    Creates a weekly or monthly report using the active config's report paths
    and log files.

    Args:
        args: Namespace with 'type' and optional 'date'/'days' parameters
            - type: Report type ("weekly" or "monthly")
            - date: Target date for report (default: today)
            - days: Compatibility flag for older weekly invocations

    Returns:
        0 on success, 1 on error

    Side Effects:
        - Creates report file in reports directory
        - May open generated report in browser

    Example:
        $ rmd report weekly
        $ rmd report weekly -d 2024-01-15
        $ rmd report monthly -d 2024-01-15
    """
    print(_t("📊 Generating report..."))

    try:
        # Import here to avoid circular dependency
        from datetime import datetime

        from schedule_management.report import generate_manual_report

        # Parse target date
        if hasattr(args, "date") and args.date:
            try:
                target_date = datetime.strptime(args.date, "%Y-%m-%d").date()
            except ValueError:
                print(_t("❌ Invalid date format: {date}").format(date=args.date))
                print(_t("   Use YYYY-MM-DD format (e.g., 2024-01-15)"))
                return 1
        else:
            target_date = None

        report_type = getattr(args, "type", None)
        if report_type not in {"weekly", "monthly"}:
            print(_t("❌ Unsupported report type: {type}").format(type=report_type))
            return 1

        days = getattr(args, "days", None)
        if report_type == "weekly":
            if days not in (None, 7):
                print(_t("❌ Custom day ranges are not supported for weekly reports."))
                print(_t("   Use '--days 7' or omit the flag."))
                return 1
        elif days is not None:
            print(_t("❌ '--days' is not supported for monthly reports."))
            return 1

        print(_t("   Report type: {type}").format(type=report_type))
        if target_date is not None:
            print(_t("   Target date: {date}").format(date=target_date))

        # Generate report
        report_path = generate_manual_report(
            report_type,
            target_date=target_date,
        )

        if report_path:
            print("\n" + _t("✅ Report generated: {path}").format(path=report_path))

            # Try to open on macOS
            if sys.platform == "darwin":
                try:
                    subprocess.run(["open", str(report_path)], check=False)
                except Exception:
                    pass  # Silent fail for opening

            return 0
        else:
            print(_t("⚠️  Report generation completed but no file was created."))
            return 1

    except ImportError as e:
        print(_t("❌ Missing dependency for report generation: {e}").format(e=e))
        return 1
    except Exception as e:
        print(_t("❌ Error generating report: {e}").format(e=e))
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
        print(_t("❌ Unknown file: {file}").format(file=target))
        print(_t("   Available: {files}").format(files=', '.join(file_map.keys())))
        return 1

    file_path = Path(file_map[target])

    if not file_path.exists():
        print(_t("⚠️  File does not exist: {path}").format(path=file_path))
        print(_t("   Creating empty file..."))
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.touch()

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
        print(_t("❌ No editor found. Set $EDITOR environment variable."))
        print(_t("   File path: {path}").format(path=file_path))
        return 1

    print(_t("📝 Opening {file} in {editor}...").format(file=target, editor=editor))

    try:
        subprocess.run([editor, str(file_path)], check=False)
        return 0
    except Exception as e:
        print(_t("❌ Could not open editor: {e}").format(e=e))
        return 1


def mode_command(args) -> int:
    """
    Handle the 'mode' command - display or switch the active mode.

    If no mode argument is provided, display the current mode.
    If 'j' or 'p' is provided, update the mode and reload/restart the reminder service.
    """
    from schedule_management.data.loaders import load_mode, save_mode

    requested_mode = getattr(args, "mode", None)
    if requested_mode is None:
        current_mode = load_mode()
        print(_t("Current mode is {mode} mode").format(mode=current_mode))
        return 0

    requested_mode = requested_mode.lower().strip()
    if requested_mode not in ("j", "p"):
        print(_t("❌ Invalid mode: {mode}. Only 'j' or 'p' is supported.").format(mode=requested_mode))
        return 1

    current_mode = load_mode()
    if current_mode == requested_mode:
        print(_t("Already in {mode} mode").format(mode=requested_mode))
        return 0

    try:
        save_mode(requested_mode)
        print(_t("✅ Mode switched to {mode} mode successfully!").format(mode=requested_mode))

        # Restart/reload the reminder service so it immediately updates its log and state
        restarted, details = _restart_reminder_service()
        if restarted:
            print(_t("✅ Reminder service restarted"))
        elif details == "No installer restart script found.":
            print(_t("ℹ️  No installer restart script found."))
            print(_t("   Restart the reminder service manually if it is already running."))
        else:
            print(_t("❌ Reminder service restart failed:"))
            print(details)
            return 1

        return 0
    except Exception as e:
        print(_t("❌ Failed to switch mode: {e}").format(e=e))
        return 1
