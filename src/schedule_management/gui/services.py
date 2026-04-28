"""
Structured service operations for the Schedule Everything desktop GUI.

This module wraps existing schedule-management storage and schedule helpers
without printing CLI tables or prompts. Functions accept JSON-like payloads and
return JSON-serializable dictionaries for the Tauri bridge.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from schedule_management.commands import status as status_commands
from schedule_management.commands.deadlines import prune_expired_deadlines
from schedule_management.commands.status import (
    get_current_and_next_events,
    get_today_schedule_for_status,
)
from schedule_management.config_layout import (
    RuntimePaths,
    preview_active_config_dir,
    resolve_config_root_dir,
)
from schedule_management.data import (
    load_deadlines,
    load_habit_records,
    load_habits,
    load_tasks,
    log_task_action,
    save_deadlines,
    save_habit_records,
    save_tasks,
)
from schedule_management.synced_schedule import (
    format_event_label,
    get_event_block_name,
    iter_syncable_slots,
    load_synced_schedule,
    synced_schedule_matches_today,
)


class GuiError(Exception):
    """Structured error for GUI bridge responses."""

    def __init__(
        self,
        code: str,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "details": self.details,
        }


def _today() -> date:
    return date.today()


def _snapshot_runtime_paths() -> RuntimePaths:
    root_dir = resolve_config_root_dir()
    active_config_dir = preview_active_config_dir(root_dir)
    active_id = 0
    if active_config_dir.name.startswith("user_config_"):
        try:
            active_id = int(active_config_dir.name.removeprefix("user_config_"))
        except ValueError:
            active_id = 0

    if not (active_config_dir / "settings.toml").exists() and (
        root_dir / "settings.toml"
    ).exists():
        active_config_dir = root_dir

    tasks_dir = root_dir / "tasks"
    return RuntimePaths(
        root_dir=root_dir,
        active_id=active_id,
        active_config_dir=active_config_dir,
        settings_path=active_config_dir / "settings.toml",
        odd_path=active_config_dir / "odd_weeks.toml",
        even_path=active_config_dir / "even_weeks.toml",
        ddl_path=active_config_dir / "ddl.json",
        habit_path=active_config_dir / "habits.toml",
        profile_path=active_config_dir / "profile.md",
        tasks_path=tasks_dir / "tasks.json",
        task_log_path=tasks_dir / "tasks.log",
        record_path=tasks_dir / "record.json",
        procrastinate_path=tasks_dir / "procrastinate.json",
    )


def _require_text(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise GuiError("invalid_input", f"{key} is required.")
    return value.strip()


def _require_priority(payload: dict[str, Any]) -> int:
    value = payload.get("priority")
    try:
        priority = int(value)
    except (TypeError, ValueError):
        raise GuiError("invalid_input", "priority must be an integer.") from None
    if priority < 1 or priority > 10:
        raise GuiError("invalid_input", "priority must be between 1 and 10.")
    return priority


def _save_tasks_or_error(tasks: list[dict[str, Any]]) -> None:
    try:
        save_tasks(tasks)
    except Exception as exc:
        raise GuiError("storage_error", f"failed to save tasks: {exc}") from exc


def _log_task_or_error(
    action: str,
    task: dict[str, Any],
    metadata: dict[str, Any] | None = None,
) -> None:
    try:
        log_task_action(action, task, metadata)
    except Exception as exc:
        raise GuiError("storage_error", f"failed to log task action: {exc}") from exc


def _save_deadlines_or_error(deadlines: list[dict[str, Any]]) -> None:
    try:
        save_deadlines(deadlines)
    except Exception as exc:
        raise GuiError("storage_error", f"failed to save deadlines: {exc}") from exc


def _save_habit_records_or_error(records: list[dict[str, Any]]) -> None:
    try:
        save_habit_records(records)
    except Exception as exc:
        raise GuiError("storage_error", f"failed to save habit records: {exc}") from exc


def _parse_deadline_date(raw_date: str) -> str:
    text = raw_date.strip()
    try:
        if "-" in text:
            parsed = datetime.strptime(text, "%Y-%m-%d").date()
            return parsed.isoformat()

        parts = text.split(".")
        if len(parts) != 2:
            raise ValueError("date must be YYYY-MM-DD or M.D")
        month = int(parts[0])
        day = int(parts[1])
        current = _today()
        parsed = date(current.year, month, day)
        if parsed < current:
            parsed = date(current.year + 1, month, day)
        return parsed.isoformat()
    except ValueError as exc:
        raise GuiError("invalid_input", f"invalid deadline date: {exc}") from exc


def _sorted_tasks() -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for task in load_tasks():
        if not isinstance(task, dict):
            continue
        description = task.get("description")
        if not isinstance(description, str) or not description.strip():
            continue
        try:
            priority = int(task.get("priority", 0))
        except (TypeError, ValueError):
            priority = 0
        normalized.append(
            {
                "description": description.strip(),
                "priority": priority,
            }
        )
    return sorted(normalized, key=lambda item: item["priority"], reverse=True)


def _deadline_status(deadline_date: date, current_date: date) -> str:
    days_left = (deadline_date - current_date).days
    if days_left < 0:
        return "overdue"
    if days_left == 0:
        return "today"
    if days_left <= 3:
        return "urgent"
    if days_left <= 7:
        return "soon"
    return "ok"


def _deadline_rows(current_date: date) -> list[dict[str, Any]]:
    deadlines, removed = prune_expired_deadlines(load_deadlines(), today=current_date)
    if removed:
        _save_deadlines_or_error(deadlines)

    rows: list[dict[str, Any]] = []
    for item in sorted(deadlines, key=lambda value: str(value.get("deadline", ""))):
        event = str(item.get("event", "")).strip()
        raw_deadline = str(item.get("deadline", "")).strip()
        if not event or not raw_deadline:
            continue
        try:
            deadline_date = datetime.strptime(raw_deadline, "%Y-%m-%d").date()
        except ValueError:
            rows.append(
                {
                    "event": event,
                    "deadline": raw_deadline,
                    "daysLeft": None,
                    "status": "invalid",
                }
            )
            continue
        rows.append(
            {
                "event": event,
                "deadline": deadline_date.isoformat(),
                "daysLeft": (deadline_date - current_date).days,
                "status": _deadline_status(deadline_date, current_date),
            }
        )
    return rows


def _habit_rows(current_date: date) -> list[dict[str, Any]]:
    habits = load_habits()
    records = load_habit_records()
    completed: dict[str, str] = {}
    for record in records:
        if record.get("date") == current_date.isoformat():
            raw_completed = record.get("completed", {})
            if isinstance(raw_completed, dict):
                completed = {str(key): str(value) for key, value in raw_completed.items()}
            break

    return [
        {
            "id": habit_id,
            "description": description,
            "completed": habit_id in completed,
        }
        for habit_id, description in sorted(habits.items())
    ]


def _schedule_rows(schedule: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for time_str in sorted(schedule):
        event = schedule[time_str]
        rows.append(
            {
                "time": time_str,
                "label": format_event_label(event),
                "block": get_event_block_name(event),
                "syncable": bool(time_str in dict(iter_syncable_slots({time_str: event}))),
            }
        )
    return rows


def status_snapshot(payload: dict[str, Any]) -> dict[str, Any]:
    del payload
    current_date = _today()
    runtime_paths = _snapshot_runtime_paths()
    status_commands.SETTINGS_PATH = str(runtime_paths.settings_path)
    status_commands.ODD_PATH = str(runtime_paths.odd_path)
    status_commands.EVEN_PATH = str(runtime_paths.even_path)

    try:
        schedule, parity, is_skipped, config = get_today_schedule_for_status()
    except Exception as exc:
        raise GuiError("config_error", f"failed to load schedule: {exc}") from exc

    current_event, next_event, time_to_next = get_current_and_next_events(
        schedule,
        config,
    )
    synced = load_synced_schedule()
    weekday = current_date.strftime("%A").lower()

    return {
        "config": {
            "rootDir": str(runtime_paths.root_dir),
            "activeId": runtime_paths.active_id,
            "activeConfigDir": str(runtime_paths.active_config_dir),
            "tasksPath": str(runtime_paths.tasks_path),
            "deadlinesPath": str(runtime_paths.ddl_path),
            "habitsPath": str(runtime_paths.habit_path),
            "recordsPath": str(runtime_paths.record_path),
        },
        "today": {
            "date": current_date.isoformat(),
            "weekday": weekday,
            "parity": parity,
        },
        "schedule": {
            "isSkipped": is_skipped,
            "current": current_event,
            "next": next_event,
            "timeToNext": time_to_next,
            "events": _schedule_rows(schedule),
            "hasSyncedOverlay": synced_schedule_matches_today(
                synced,
                target_date=current_date,
                parity=parity,
                weekday=weekday,
            ),
        },
        "tasks": _sorted_tasks(),
        "deadlines": _deadline_rows(current_date),
        "habits": _habit_rows(current_date),
    }


def task_add(payload: dict[str, Any]) -> dict[str, Any]:
    description = _require_text(payload, "description")
    priority = _require_priority(payload)
    tasks = load_tasks()
    new_task = {"description": description, "priority": priority}

    existing_index = None
    for index, task in enumerate(tasks):
        if task.get("description") == description:
            existing_index = index
            break

    if existing_index is None:
        tasks.append(new_task)
        log_action = "added"
        metadata = None
    else:
        old_priority = tasks[existing_index].get("priority")
        tasks[existing_index] = new_task
        log_action = "updated"
        metadata = {"old_priority": old_priority}

    _save_tasks_or_error(tasks)
    _log_task_or_error(log_action, new_task, metadata)
    return new_task


def task_update(payload: dict[str, Any]) -> dict[str, Any]:
    original_description = _require_text(payload, "originalDescription")
    description = _require_text(payload, "description")
    priority = _require_priority(payload)
    tasks = load_tasks()

    for task in tasks:
        if (
            task.get("description") == description
            and task.get("description") != original_description
        ):
            raise GuiError("duplicate", f"task already exists: {description}")

    for index, task in enumerate(tasks):
        if task.get("description") == original_description:
            updated = {"description": description, "priority": priority}
            old_task = dict(task)
            tasks[index] = updated
            _save_tasks_or_error(tasks)
            _log_task_or_error("updated", updated, {"old_task": old_task})
            return updated

    raise GuiError("not_found", f"task not found: {original_description}")


def task_delete(payload: dict[str, Any]) -> dict[str, Any]:
    description = _require_text(payload, "description")
    tasks = load_tasks()
    deleted = [task for task in tasks if task.get("description") == description]
    if not deleted:
        raise GuiError("not_found", f"task not found: {description}")

    remaining = [task for task in tasks if task.get("description") != description]
    _save_tasks_or_error(remaining)
    for task in deleted:
        _log_task_or_error("deleted", dict(task))
    return {"description": description, "deleted": len(deleted)}


def deadline_add(payload: dict[str, Any]) -> dict[str, Any]:
    event = _require_text(payload, "event")
    deadline = _parse_deadline_date(_require_text(payload, "date"))
    deadlines = load_deadlines()
    new_deadline = {
        "event": event,
        "deadline": deadline,
        "added": datetime.now(timezone.utc).isoformat(),
    }

    existing_index = None
    for index, item in enumerate(deadlines):
        if item.get("event") == event:
            existing_index = index
            break
    if existing_index is None:
        deadlines.append(new_deadline)
    else:
        deadlines[existing_index] = new_deadline
    _save_deadlines_or_error(deadlines)
    return new_deadline


def deadline_update(payload: dict[str, Any]) -> dict[str, Any]:
    original_event = _require_text(payload, "originalEvent")
    event = _require_text(payload, "event")
    deadline = _parse_deadline_date(_require_text(payload, "date"))
    deadlines = load_deadlines()

    for item in deadlines:
        if item.get("event") == event and item.get("event") != original_event:
            raise GuiError("duplicate", f"deadline already exists: {event}")

    for index, item in enumerate(deadlines):
        if item.get("event") == original_event:
            updated = {
                "event": event,
                "deadline": deadline,
                "added": str(item.get("added") or datetime.now(timezone.utc).isoformat()),
            }
            deadlines[index] = updated
            _save_deadlines_or_error(deadlines)
            return updated

    raise GuiError("not_found", f"deadline not found: {original_event}")


def deadline_delete(payload: dict[str, Any]) -> dict[str, Any]:
    event = _require_text(payload, "event")
    deadlines = load_deadlines()
    deleted = [item for item in deadlines if item.get("event") == event]
    if not deleted:
        raise GuiError("not_found", f"deadline not found: {event}")
    remaining = [item for item in deadlines if item.get("event") != event]
    _save_deadlines_or_error(remaining)
    return {"event": event, "deleted": len(deleted)}


def habit_mark(payload: dict[str, Any]) -> dict[str, Any]:
    raw_ids = payload.get("habitIds", [])
    if not isinstance(raw_ids, list):
        raise GuiError("invalid_input", "habitIds must be a list.")

    habits = load_habits()
    valid_ids: list[str] = []
    invalid_ids: list[str] = []
    for raw_id in raw_ids:
        habit_id = str(raw_id)
        if habit_id in habits:
            valid_ids.append(habit_id)
        else:
            invalid_ids.append(habit_id)

    if invalid_ids:
        raise GuiError(
            "invalid_input",
            "one or more habit IDs are invalid.",
            {"invalidIds": invalid_ids},
        )

    current_date = _today().isoformat()
    completed = {habit_id: habits[habit_id] for habit_id in valid_ids}
    records = load_habit_records()
    new_record = {
        "date": current_date,
        "completed": completed,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    for index, record in enumerate(records):
        if record.get("date") == current_date:
            records[index] = new_record
            break
    else:
        records.append(new_record)

    _save_habit_records_or_error(records)
    return new_record
