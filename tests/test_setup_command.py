"""Tests for the `reminder setup` command flow and helpers."""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import schedule_management.commands.setup as setup_cmd_module
from schedule_management.commands.setup import (
    LLMConfig,
    has_completed_configuration,
    load_llm_config,
    save_llm_config,
    setup_command,
)
from schedule_management.commands.setup_prompts import (
    BUILD_SYSTEM_PROMPT,
    MODIFY_SYSTEM_PROMPT,
    render_build_user_prompt,
    render_modify_user_prompt,
    render_retry_user_prompt,
)
from schedule_management.cli import create_parser


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_has_completed_configuration_true(tmp_path):
    _write(
        tmp_path / "settings.toml",
        """
[settings]

[time_blocks]

[time_points]

[tasks]

[paths]
""".strip()
        + "\n",
    )
    _write(
        tmp_path / "odd_weeks.toml",
        """
[monday]
"09:00" = "focus"

[common]
""".strip()
        + "\n",
    )
    _write(
        tmp_path / "even_weeks.toml",
        """
[monday]
"09:00" = "focus"

[common]
""".strip()
        + "\n",
    )
    _write(tmp_path / "habits.toml", '[habits]\n1 = "Read"\n')

    complete, reason = has_completed_configuration(tmp_path)

    assert complete is True
    assert reason == "ok"


def test_has_completed_configuration_missing_file(tmp_path):
    _write(tmp_path / "settings.toml", "[settings]\n")

    complete, reason = has_completed_configuration(tmp_path)

    assert complete is False
    assert "Missing" in reason


def test_has_completed_configuration_invalid_toml(tmp_path):
    _write(tmp_path / "settings.toml", "[settings]\n")
    _write(tmp_path / "odd_weeks.toml", "[monday]\n")
    _write(tmp_path / "even_weeks.toml", "[monday]\n")
    _write(tmp_path / "habits.toml", "[habits\n")

    complete, reason = has_completed_configuration(tmp_path)

    assert complete is False
    assert "Invalid TOML" in reason


def test_llm_config_round_trip(tmp_path):
    config_path = tmp_path / "llm.toml"
    expected = LLMConfig(
        vendor="openai_compatible",
        model="gpt-4.1-mini",
        api_key="secret-key",
        base_url="https://example.com/v1",
    )

    save_llm_config(config_path, expected)
    loaded = load_llm_config(config_path)

    assert loaded == expected


def test_openai_generation_streams_responses_api():
    llm_client = setup_cmd_module.LLMClient(
        LLMConfig(vendor="openai", model="gpt-4.1-mini", api_key="secret")
    )

    class FakeOpenAIStream:
        def __init__(self):
            self._events = [
                SimpleNamespace(type="response.output_text.delta", delta='{"ok": '),
                SimpleNamespace(type="response.output_text.delta", delta="true}"),
            ]
            self._final_response = SimpleNamespace(output_text='{"ok": true}')

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            return False

        def __iter__(self):
            return iter(self._events)

        def get_final_response(self):
            return self._final_response

    fake_client = MagicMock()
    fake_client.responses.stream.return_value = FakeOpenAIStream()

    with patch.object(
        setup_cmd_module.LLMClient,
        "_get_openai_client",
        return_value=fake_client,
    ):
        streamed_chunks: list[str] = []
        result = llm_client.generate("system", "user", on_text=streamed_chunks.append)

    assert result == '{"ok": true}'
    assert "".join(streamed_chunks) == '{"ok": true}'
    fake_client.responses.stream.assert_called_once()
    fake_client.chat.completions.create.assert_not_called()


def test_anthropic_generation_streams_text_chunks():
    llm_client = setup_cmd_module.LLMClient(
        LLMConfig(vendor="anthropic", model="claude-sonnet", api_key="secret")
    )

    class FakeAnthropicStream:
        def __init__(self):
            self.text_stream = iter(['{"ok": ', "true}"])

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            return False

        def get_final_message(self):
            return {"content": [{"type": "text", "text": '{"ok": true}'}]}

    fake_client = MagicMock()
    fake_client.messages.stream.return_value = FakeAnthropicStream()

    with patch.object(
        setup_cmd_module.LLMClient,
        "_get_anthropic_client",
        return_value=fake_client,
    ):
        streamed_chunks: list[str] = []
        result = llm_client.generate("system", "user", on_text=streamed_chunks.append)

    assert result == '{"ok": true}'
    assert "".join(streamed_chunks) == '{"ok": true}'
    fake_client.messages.stream.assert_called_once()


def test_gemini_generation_streams_text_chunks():
    llm_client = setup_cmd_module.LLMClient(
        LLMConfig(vendor="gemini", model="gemini-2.5-flash", api_key="secret")
    )

    fake_client = MagicMock()
    fake_client.models.generate_content_stream.return_value = [
        SimpleNamespace(text='{"ok": '),
        SimpleNamespace(text="true}"),
    ]

    with patch.object(
        setup_cmd_module.LLMClient,
        "_get_gemini_client",
        return_value=fake_client,
    ):
        streamed_chunks: list[str] = []
        result = llm_client.generate("system", "user", on_text=streamed_chunks.append)

    assert result == '{"ok": true}'
    assert "".join(streamed_chunks) == '{"ok": true}'
    fake_client.models.generate_content_stream.assert_called_once()


def test_setup_command_routes_to_modify_when_config_exists(tmp_path):
    llm = LLMConfig(vendor="openai", model="gpt-4.1-mini", api_key="k")

    with (
        patch(
            "schedule_management.commands.setup.ensure_llm_config",
            return_value=llm,
        ),
        patch(
            "schedule_management.commands.setup._resolve_config_dir",
            return_value=tmp_path,
        ),
        patch(
            "schedule_management.commands.setup.has_completed_configuration",
            return_value=(True, "ok"),
        ),
        patch("schedule_management.commands.setup._ask_yes_no", return_value=True),
        patch(
            "schedule_management.commands.setup.modify_schedule_agent",
            return_value=0,
        ) as modify_mock,
    ):
        result = setup_command(MagicMock())

    assert result == 0
    modify_mock.assert_called_once_with(llm, tmp_path)


def test_setup_command_routes_to_build_when_config_missing(tmp_path):
    llm = LLMConfig(vendor="openai", model="gpt-4.1-mini", api_key="k")

    with (
        patch(
            "schedule_management.commands.setup.ensure_llm_config",
            return_value=llm,
        ),
        patch(
            "schedule_management.commands.setup._resolve_config_dir",
            return_value=tmp_path,
        ),
        patch(
            "schedule_management.commands.setup.has_completed_configuration",
            return_value=(False, "Missing settings.toml"),
        ),
        patch("schedule_management.commands.setup._ask_yes_no", return_value=True),
        patch(
            "schedule_management.commands.setup.build_schedule_agent",
            return_value=0,
        ) as build_mock,
    ):
        result = setup_command(MagicMock())

    assert result == 0
    build_mock.assert_called_once_with(llm, tmp_path)


def test_setup_command_is_registered_in_parser():
    parser = create_parser()

    args = parser.parse_args(["setup"])

    assert args.command == "setup"
    assert args.func.__name__ == "setup_command"


def test_prompt_templates_include_required_keys():
    for prompt in (BUILD_SYSTEM_PROMPT, MODIFY_SYSTEM_PROMPT):
        assert "conversation" in prompt
        assert "needs_user_input" in prompt
        assert "question_to_user" in prompt
        assert "settings_toml" in prompt
        assert "odd_weeks_toml" in prompt
        assert "even_weeks_toml" in prompt


def test_prompt_renderers_include_context_sections(tmp_path):
    build_prompt = render_build_user_prompt(
        tmp_path,
        description="Classes on monday and wednesday mornings.",
        attachment_name="timetable.png",
        conversation_history="Assistant: Got it\nUser: Please keep evenings free.",
    )
    assert "Target config directory" in build_prompt
    assert "timetable.png" in build_prompt
    assert "Conversation history" in build_prompt

    modify_prompt = render_modify_user_prompt(
        "Move gym to evenings",
        "[settings.toml]\n[settings]\n",
        conversation_history="Assistant: Do you prefer weekdays?\nUser: Tuesday/Thursday.",
    )
    assert "Change request" in modify_prompt
    assert "Current configuration files" in modify_prompt
    assert "Conversation history" in modify_prompt

    retry_prompt = render_retry_user_prompt(
        original_user_prompt="Original task",
        parse_error="missing key",
        previous_response='{"foo": "bar"}',
    )
    assert "Parse error" in retry_prompt
    assert "Return corrected JSON only." in retry_prompt


def test_parse_agent_turn_requires_conversation_and_toml_when_ready():
    response = (
        "{"
        '"conversation": "I applied your update and generated files.", '
        '"needs_user_input": false, '
        '"actions": ["analyzed request", "prepared output"], '
        '"settings_toml": "[settings]\\n\\n[time_blocks]\\n\\n[time_points]\\n\\n[tasks]\\n\\n[paths]\\n", '
        '"odd_weeks_toml": "[monday]\\n\\"09:00\\" = \\"study\\"\\n\\n[common]\\n", '
        '"even_weeks_toml": "[monday]\\n\\"09:00\\" = \\"study\\"\\n\\n[common]\\n"'
        "}"
    )

    turn, error = setup_cmd_module._parse_agent_turn(response)

    assert error is None
    assert turn is not None
    assert turn.conversation.startswith("I applied")
    assert turn.needs_user_input is False
    assert turn.bundle is not None
    assert "settings.toml" in turn.bundle


def test_parse_agent_turn_supports_missing_information_questions():
    response = (
        "{"
        '"conversation": "I need one more detail before I can finish.", '
        '"needs_user_input": true, '
        '"question_to_user": "Which days should stay completely free?", '
        '"missing_information": ["free days preference"], '
        '"actions": ["validated constraints"]'
        "}"
    )

    turn, error = setup_cmd_module._parse_agent_turn(response)

    assert error is None
    assert turn is not None
    assert turn.needs_user_input is True
    assert turn.bundle is None
    assert turn.question_to_user == "Which days should stay completely free?"
    assert turn.missing_information == ["free days preference"]
