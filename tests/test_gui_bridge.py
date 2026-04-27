from __future__ import annotations

import json


def test_dispatch_returns_success(monkeypatch):
    from schedule_management.gui import bridge

    monkeypatch.setitem(
        bridge.COMMANDS,
        "example",
        lambda payload: {"echo": payload["value"]},
    )

    response = bridge.dispatch({"command": "example", "payload": {"value": "ok"}})

    assert response == {"ok": True, "data": {"echo": "ok"}}


def test_dispatch_returns_structured_gui_error(monkeypatch):
    from schedule_management.gui import bridge
    from schedule_management.gui.services import GuiError

    def raise_error(payload):
        raise GuiError("invalid_input", "bad input", {"field": "name"})

    monkeypatch.setitem(bridge.COMMANDS, "broken", raise_error)

    response = bridge.dispatch({"command": "broken", "payload": {}})

    assert response["ok"] is False
    assert response["error"]["code"] == "invalid_input"
    assert response["error"]["message"] == "bad input"
    assert response["error"]["details"] == {"field": "name"}


def test_dispatch_rejects_unknown_command():
    from schedule_management.gui import bridge

    response = bridge.dispatch({"command": "missing", "payload": {}})

    assert response["ok"] is False
    assert response["error"]["code"] == "unknown_command"


def test_main_reads_json_from_argument(capsys, monkeypatch):
    from schedule_management.gui import bridge

    monkeypatch.setitem(
        bridge.COMMANDS,
        "example",
        lambda payload: {"echo": payload["value"]},
    )

    exit_code = bridge.main(
        ['{"command": "example", "payload": {"value": "hello"}}']
    )

    assert exit_code == 0
    output = json.loads(capsys.readouterr().out)
    assert output == {"ok": True, "data": {"echo": "hello"}}
