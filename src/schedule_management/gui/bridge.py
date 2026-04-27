"""
JSON command bridge for the Tauri desktop app.

The bridge accepts one JSON request and writes one JSON response. It avoids rich
console output so the Rust side can parse responses reliably.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Callable
from typing import Any

from schedule_management.commands.sync import accept_sync_plan, generate_sync_proposal
from schedule_management.gui.services import (
    GuiError,
    deadline_add,
    deadline_delete,
    deadline_update,
    habit_mark,
    status_snapshot,
    task_add,
    task_delete,
    task_update,
)

BridgeHandler = Callable[[dict[str, Any]], dict[str, Any]]

COMMANDS: dict[str, BridgeHandler] = {
    "status_snapshot": status_snapshot,
    "task_add": task_add,
    "task_update": task_update,
    "task_delete": task_delete,
    "deadline_add": deadline_add,
    "deadline_update": deadline_update,
    "deadline_delete": deadline_delete,
    "habit_mark": habit_mark,
    "sync_generate": lambda payload: generate_sync_proposal(
        _coerce_feedback(payload.get("feedback", []))
    ),
    "sync_accept": lambda payload: accept_sync_plan(_coerce_plan(payload)),
}


def _coerce_feedback(value: Any) -> list[str]:
    if not isinstance(value, list):
        raise GuiError("invalid_input", "feedback must be a list.")
    return [str(item).strip() for item in value if str(item).strip()]


def _coerce_plan(payload: dict[str, Any]) -> dict[str, Any]:
    plan = payload.get("plan")
    if not isinstance(plan, dict):
        raise GuiError("invalid_input", "plan is required.")
    return plan


def _error_response(
    code: str,
    message: str,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "ok": False,
        "error": {
            "code": code,
            "message": message,
            "details": details or {},
        },
    }


def dispatch(request: dict[str, Any]) -> dict[str, Any]:
    command = request.get("command")
    payload = request.get("payload", {})
    if not isinstance(command, str) or not command.strip():
        return _error_response("invalid_request", "command is required.")
    if not isinstance(payload, dict):
        return _error_response("invalid_request", "payload must be an object.")

    handler = COMMANDS.get(command)
    if handler is None:
        return _error_response("unknown_command", f"unknown command: {command}")

    try:
        return {"ok": True, "data": handler(payload)}
    except GuiError as exc:
        return {"ok": False, "error": exc.to_dict()}
    except Exception as exc:
        return _error_response("internal_error", str(exc))


def _read_request(argv: list[str]) -> dict[str, Any]:
    raw_request = argv[0] if argv else sys.stdin.read()
    try:
        request = json.loads(raw_request)
    except json.JSONDecodeError as exc:
        raise GuiError("invalid_json", f"invalid JSON request: {exc}") from exc
    if not isinstance(request, dict):
        raise GuiError("invalid_request", "request must be an object.")
    return request


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    try:
        request = _read_request(args)
        response = dispatch(request)
    except GuiError as exc:
        response = {"ok": False, "error": exc.to_dict()}
    print(json.dumps(response, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
