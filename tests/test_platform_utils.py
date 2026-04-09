import schedule_management.platform as platform_utils


def test_get_platform_detects_macos(monkeypatch):
    monkeypatch.setattr(platform_utils.sys, "platform", "darwin")
    assert platform_utils.get_platform() == "macos"


def test_get_platform_detects_linux(monkeypatch):
    monkeypatch.setattr(platform_utils.sys, "platform", "linux")
    assert platform_utils.get_platform() == "linux"


def test_get_platform_detects_windows(monkeypatch):
    monkeypatch.setattr(platform_utils.sys, "platform", "win32")
    assert platform_utils.get_platform() == "windows"


def test_get_platform_handles_unknown_values(monkeypatch):
    monkeypatch.setattr(platform_utils.sys, "platform", "plan9")
    assert platform_utils.get_platform() == "unknown"
