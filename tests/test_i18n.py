"""Unit tests for the bilingual/i18n module."""

import os
from unittest.mock import patch, mock_open
from pathlib import Path
import pytest

from schedule_management.i18n import get_language, _t


def test_i18n_default_language_is_english(monkeypatch):
    """Test that the default language is English when no env or setting is configured."""
    monkeypatch.delenv("REMINDER_LANG", raising=False)

    # Mock resolve_runtime_paths to point to a non-existent settings file to force default
    with patch("schedule_management.i18n.resolve_runtime_paths") as mock_resolve:
        mock_resolve.return_value.settings_path = Path("/nonexistent/settings.toml")
        assert get_language() == "en"
        assert _t("📋 No tasks found") == "📋 No tasks found"


def test_i18n_env_variable_overrides_settings(monkeypatch):
    """Test that the REMINDER_LANG environment variable overrides other settings."""
    # 1. Test Chinese environment override
    monkeypatch.setenv("REMINDER_LANG", "zh")
    assert get_language() == "zh"
    assert _t("📋 No tasks found") == "📋 未找到任务"

    # Test alternate forms like cn, chinese, uppercase ZH
    monkeypatch.setenv("REMINDER_LANG", "cn")
    assert get_language() == "zh"
    monkeypatch.setenv("REMINDER_LANG", "Chinese")
    assert get_language() == "zh"
    monkeypatch.setenv("REMINDER_LANG", "ZH")
    assert get_language() == "zh"

    # 2. Test English environment override
    monkeypatch.setenv("REMINDER_LANG", "en")
    assert get_language() == "en"
    assert _t("📋 No tasks found") == "📋 No tasks found"


def test_i18n_toml_settings_configuration(monkeypatch):
    """Test that the language setting is correctly loaded from settings.toml when env is not set."""
    monkeypatch.delenv("REMINDER_LANG", raising=False)

    # 1. Chinese configured in settings.toml
    mock_toml_zh = b"""
    [settings]
    language = "zh"
    """
    with patch("schedule_management.i18n.resolve_runtime_paths") as mock_resolve:
        mock_resolve.return_value.settings_path = Path("/mock/settings.toml")
        with patch("builtins.open", mock_open(read_data=mock_toml_zh)):
            with patch("pathlib.Path.exists", return_value=True):
                assert get_language() == "zh"
                assert _t("📋 No tasks found") == "📋 未找到任务"

    # 2. English configured in settings.toml
    mock_toml_en = b"""
    [settings]
    language = "en"
    """
    with patch("schedule_management.i18n.resolve_runtime_paths") as mock_resolve:
        mock_resolve.return_value.settings_path = Path("/mock/settings.toml")
        with patch("builtins.open", mock_open(read_data=mock_toml_en)):
            with patch("pathlib.Path.exists", return_value=True):
                assert get_language() == "en"
                assert _t("📋 No tasks found") == "📋 No tasks found"


def test_i18n_dynamic_formatting(monkeypatch):
    """Test that dynamic strings are correctly formatted with variables after translation."""
    # English mode formatting
    monkeypatch.setenv("REMINDER_LANG", "en")
    en_msg = _t("✅ Task '{task_description}' updated! Priority changed from {old_priority} to {priority}").format(
        task_description="Testing i18n", old_priority=3, priority=7
    )
    assert en_msg == "✅ Task 'Testing i18n' updated! Priority changed from 3 to 7"

    # Chinese mode formatting
    monkeypatch.setenv("REMINDER_LANG", "zh")
    zh_msg = _t("✅ Task '{task_description}' updated! Priority changed from {old_priority} to {priority}").format(
        task_description="Testing i18n", old_priority=3, priority=7
    )
    assert zh_msg == "✅ 任务 'Testing i18n' 已更新！优先级从 3 修改为 7"


def test_i18n_fallback_for_missing_translation(monkeypatch):
    """Test that _t returns the original string as a fallback when a key is missing from translation."""
    monkeypatch.setenv("REMINDER_LANG", "zh")
    missing_key = "This string is not inside our ZH_TRANSLATIONS dictionary!"
    assert _t(missing_key) == missing_key
