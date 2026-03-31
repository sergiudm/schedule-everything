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


def test_local_file_tools_can_read_and_edit(tmp_path):
    tools = setup_cmd_module.LocalFileTools(allowed_roots=[tmp_path])
    source = tmp_path / "notes.txt"
    source.write_text("alpha\nbeta\n", encoding="utf-8")

    read_result = tools.execute(
        "read_file",
        {
            "path": str(source),
            "start_line": 2,
            "end_line": 2,
        },
    )
    assert read_result["ok"] is True
    assert read_result["content"] == "beta"

    replace_result = tools.execute(
        "replace_in_file",
        {
            "path": str(source),
            "old_text": "beta",
            "new_text": "gamma",
        },
    )
    assert replace_result["ok"] is True
    assert "gamma" in source.read_text(encoding="utf-8")

    write_result = tools.execute(
        "write_file",
        {
            "path": str(tmp_path / "created.txt"),
            "content": "hello",
        },
    )
    assert write_result["ok"] is True
    assert (tmp_path / "created.txt").read_text(encoding="utf-8") == "hello"

    blocked = tools.execute("read_file", {"path": "/etc/hosts"})
    assert blocked["ok"] is False


def test_openai_generation_supports_function_tools(tmp_path):
    llm_client = setup_cmd_module.LLMClient(
        LLMConfig(vendor="openai", model="gpt-4.1-mini", api_key="secret")
    )
    tools = setup_cmd_module.LocalFileTools(allowed_roots=[tmp_path])
    target = tmp_path / "plan.txt"
    target.write_text("line-1\nline-2\n", encoding="utf-8")

    class FakeOpenAIStream:
        def __init__(self, events, final_response):
            self._events = events
            self._final_response = final_response

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            return False

        def __iter__(self):
            return iter(self._events)

        def get_final_response(self):
            return self._final_response

    first_response = {
        "id": "resp_1",
        "output": [
            {
                "type": "function_call",
                "call_id": "call_1",
                "name": "read_file",
                "arguments": '{"path": "' + str(target) + '"}',
            }
        ],
    }
    second_response = {"id": "resp_2", "output_text": '{"ok": true}'}

    fake_client = MagicMock()
    fake_client.responses.stream.side_effect = [
        FakeOpenAIStream([], first_response),
        FakeOpenAIStream(
            [SimpleNamespace(type="response.output_text.delta", delta='{"ok": true}')],
            second_response,
        ),
    ]

    with patch.object(
        setup_cmd_module.LLMClient,
        "_get_openai_client",
        return_value=fake_client,
    ):
        result = llm_client.generate("system", "user", file_tools=tools)

    assert result == '{"ok": true}'
    assert fake_client.responses.stream.call_count == 2

    first_call_kwargs = fake_client.responses.stream.call_args_list[0].kwargs
    assert "tools" in first_call_kwargs

    second_call_kwargs = fake_client.responses.stream.call_args_list[1].kwargs
    assert second_call_kwargs["previous_response_id"] == "resp_1"
    assert second_call_kwargs["input"][0]["type"] == "function_call_output"


def test_openai_generation_passes_image_to_vision_input(tmp_path):
    llm_client = setup_cmd_module.LLMClient(
        LLMConfig(vendor="openai", model="gpt-4.1-mini", api_key="secret")
    )

    class FakeOpenAIStream:
        def __init__(self):
            self._final_response = {"id": "resp_vision", "output_text": '{"ok": true}'}

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            return False

        def __iter__(self):
            return iter([])

        def get_final_response(self):
            return self._final_response

    fake_client = MagicMock()
    fake_client.responses.stream.return_value = FakeOpenAIStream()

    attachment = setup_cmd_module.SourceAttachment(
        path=tmp_path / "plan.png",
        mime_type="image/png",
        image_base64="aGVsbG8=",
    )

    with patch.object(
        setup_cmd_module.LLMClient,
        "_get_openai_client",
        return_value=fake_client,
    ):
        result = llm_client.generate("system", "user", attachment=attachment)

    assert result == '{"ok": true}'
    call_kwargs = fake_client.responses.stream.call_args.kwargs
    user_parts = call_kwargs["input"][0]["content"]
    image_part = next(part for part in user_parts if part["type"] == "input_image")
    assert image_part["image_url"].startswith("data:image/png;base64,")


def test_anthropic_generation_supports_tool_use(tmp_path):
    llm_client = setup_cmd_module.LLMClient(
        LLMConfig(vendor="anthropic", model="claude-sonnet", api_key="secret")
    )
    tools = setup_cmd_module.LocalFileTools(allowed_roots=[tmp_path])
    target = tmp_path / "guide.txt"
    target.write_text("sample", encoding="utf-8")

    class FakeAnthropicStream:
        def __init__(self, text_chunks, final_message):
            self.text_stream = iter(text_chunks)
            self._final_message = final_message

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            return False

        def get_final_message(self):
            return self._final_message

    fake_client = MagicMock()
    fake_client.messages.stream.side_effect = [
        FakeAnthropicStream(
            [],
            {
                "content": [
                    {
                        "type": "tool_use",
                        "id": "tool_1",
                        "name": "read_file",
                        "input": {"path": str(target)},
                    }
                ]
            },
        ),
        FakeAnthropicStream(
            ['{"ok": true}'],
            {"content": [{"type": "text", "text": '{"ok": true}'}]},
        ),
    ]

    with patch.object(
        setup_cmd_module.LLMClient,
        "_get_anthropic_client",
        return_value=fake_client,
    ):
        result = llm_client.generate("system", "user", file_tools=tools)

    assert result == '{"ok": true}'
    assert fake_client.messages.stream.call_count == 2


def test_anthropic_generation_passes_image_to_vision_input(tmp_path):
    llm_client = setup_cmd_module.LLMClient(
        LLMConfig(vendor="anthropic", model="claude-sonnet", api_key="secret")
    )

    class FakeAnthropicStream:
        def __init__(self):
            self.text_stream = iter(['{"ok": true}'])

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            return False

        def get_final_message(self):
            return {"content": [{"type": "text", "text": '{"ok": true}'}]}

    fake_client = MagicMock()
    fake_client.messages.stream.return_value = FakeAnthropicStream()

    attachment = setup_cmd_module.SourceAttachment(
        path=tmp_path / "plan.png",
        mime_type="image/png",
        image_base64="aGVsbG8=",
    )

    with patch.object(
        setup_cmd_module.LLMClient,
        "_get_anthropic_client",
        return_value=fake_client,
    ):
        result = llm_client.generate("system", "user", attachment=attachment)

    assert result == '{"ok": true}'
    call_kwargs = fake_client.messages.stream.call_args.kwargs
    content_blocks = call_kwargs["messages"][0]["content"]
    image_block = next(block for block in content_blocks if block["type"] == "image")
    assert image_block["source"]["media_type"] == "image/png"


def test_gemini_generation_passes_image_to_vision_input(tmp_path):
    llm_client = setup_cmd_module.LLMClient(
        LLMConfig(vendor="gemini", model="gemini-2.5-flash", api_key="secret")
    )

    fake_client = MagicMock()
    fake_client.models.generate_content_stream.return_value = [
        SimpleNamespace(text='{"ok": true}', function_calls=None)
    ]

    attachment = setup_cmd_module.SourceAttachment(
        path=tmp_path / "plan.png",
        mime_type="image/png",
        image_base64="aGVsbG8=",
    )

    from google.genai import types as genai_types

    original_from_bytes = genai_types.Part.from_bytes

    with (
        patch.object(
            setup_cmd_module.LLMClient,
            "_get_gemini_client",
            return_value=fake_client,
        ),
        patch(
            "google.genai.types.Part.from_bytes",
            wraps=original_from_bytes,
        ) as from_bytes_mock,
    ):
        result = llm_client.generate("system", "user", attachment=attachment)

    assert result == '{"ok": true}'
    from_bytes_mock.assert_called_once()
    assert from_bytes_mock.call_args.kwargs["mime_type"] == "image/png"


def test_load_source_attachment_detects_image_without_image_extension(tmp_path):
    raw_png = b"\x89PNG\r\n\x1a\n" + b"x" * 16
    path = tmp_path / "upload.bin"
    path.write_bytes(raw_png)

    attachment, error = setup_cmd_module._load_source_attachment(path)

    assert error is None
    assert attachment is not None
    assert attachment.image_base64 is not None
    assert attachment.mime_type == "image/png"


def test_resolve_source_path_input_finds_common_downloads(tmp_path, monkeypatch):
    home = tmp_path / "home"
    downloads = home / "Downloads"
    downloads.mkdir(parents=True)

    target = downloads / "50499A1ABA0EFC793F82A8F910B3FC3C.png"
    target.write_bytes(b"\x89PNG\r\n\x1a\n" + b"x" * 16)

    workdir = tmp_path / "workspace"
    workdir.mkdir(parents=True)
    monkeypatch.chdir(workdir)

    with patch("pathlib.Path.home", return_value=home):
        resolved = setup_cmd_module._resolve_source_path_input(target.name)

    assert resolved == target


def test_turn_requests_manual_image_transcription_detection():
    turn = setup_cmd_module.AgentTurn(
        phase="discovery",
        conversation="I'm sorry, but I cannot see images.",
        needs_user_input=True,
        question_to_user=(
            "Could you describe the changes you'd like to make based on the image?"
        ),
        missing_information=["Details of the schedule changes from the image"],
    )

    assert setup_cmd_module._turn_requests_manual_image_transcription(turn) is True

    quality_turn = setup_cmd_module.AgentTurn(
        phase="discovery",
        conversation="I can see the image but the text is blurry in two cells.",
        needs_user_input=True,
        question_to_user="Could you confirm the Tuesday 14:00 course name?",
        missing_information=["Tuesday 14:00 course label"],
    )

    assert (
        setup_cmd_module._turn_requests_manual_image_transcription(quality_turn)
        is False
    )


def test_gemini_generation_supports_function_calls(tmp_path):
    llm_client = setup_cmd_module.LLMClient(
        LLMConfig(vendor="gemini", model="gemini-2.5-flash", api_key="secret")
    )
    tools = setup_cmd_module.LocalFileTools(allowed_roots=[tmp_path])
    target = tmp_path / "prefs.txt"
    target.write_text("hello", encoding="utf-8")

    fake_client = MagicMock()
    fake_client.models.generate_content_stream.side_effect = [
        iter(
            [
                SimpleNamespace(
                    text=None,
                    function_calls=[
                        SimpleNamespace(
                            id="call_1",
                            name="read_file",
                            args={"path": str(target)},
                        )
                    ],
                )
            ]
        ),
        iter([SimpleNamespace(text='{"ok": true}', function_calls=None)]),
    ]

    with patch.object(
        setup_cmd_module.LLMClient,
        "_get_gemini_client",
        return_value=fake_client,
    ):
        result = llm_client.generate("system", "user", file_tools=tools)

    assert result == '{"ok": true}'
    assert fake_client.models.generate_content_stream.call_count == 2


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
        assert "phase" in prompt
        assert "conversation" in prompt
        assert "needs_user_input" in prompt
        assert "question_to_user" in prompt
        assert "schedule_summary" in prompt
        assert "settings_toml" in prompt
        assert "odd_weeks_toml" in prompt
        assert "even_weeks_toml" in prompt
        assert "read_file" in prompt
        assert "write_file" in prompt

    assert "Never say you cannot see/view images" in BUILD_SYSTEM_PROMPT


def test_prompt_renderers_include_context_sections(tmp_path):
    build_prompt = render_build_user_prompt(
        tmp_path,
        description="Classes on monday and wednesday mornings.",
        attachment_name="timetable.png",
        conversation_history="Assistant: Got it\nUser: Please keep evenings free.",
    )
    assert "Target config directory" in build_prompt
    assert "timetable.png" in build_prompt
    assert "Image vision input status" in build_prompt
    assert "Conversation history" in build_prompt

    summary_gate_prompt = render_build_user_prompt(
        tmp_path,
        description="draft",
        attachment_name=None,
        summary_presented=False,
        summary_confirmed=False,
    )
    assert "Do NOT output any *_toml fields yet." in summary_gate_prompt

    final_gate_prompt = render_build_user_prompt(
        tmp_path,
        description="draft",
        attachment_name=None,
        summary_presented=True,
        summary_confirmed=True,
        latest_summary="Weekday deep-work mornings.",
    )
    assert "Return complete TOML now." in final_gate_prompt

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


def test_request_agent_turn_keeps_image_attachment_on_retry(tmp_path):
    attachment = setup_cmd_module.SourceAttachment(
        path=tmp_path / "plan.png",
        mime_type="image/png",
        image_base64="aGVsbG8=",
    )

    class FakeClient:
        def __init__(self):
            self.calls = 0
            self.attachments: list[setup_cmd_module.SourceAttachment | None] = []

        def generate(self, _sys, _usr, attachment=None, **_kwargs):
            self.calls += 1
            self.attachments.append(attachment)
            if self.calls == 1:
                return "not json"
            return (
                "{"
                '"phase": "discovery", '
                '"conversation": "Need one more detail.", '
                '"needs_user_input": true, '
                '"question_to_user": "What is your commute time?"'
                "}"
            )

    fake_client = FakeClient()
    turn, error = setup_cmd_module._request_agent_turn(
        fake_client,
        "system",
        "user",
        attachment=attachment,
    )

    assert error is None
    assert turn is not None
    assert fake_client.calls == 2
    assert fake_client.attachments == [attachment, attachment]


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


def test_parse_agent_turn_requires_schedule_summary_in_summary_phase():
    response = (
        "{"
        '"phase": "summary", '
        '"conversation": "Here is the draft plan overview.", '
        '"needs_user_input": true, '
        '"question_to_user": "Do you want me to generate the TOML files now?"'
        "}"
    )

    turn, error = setup_cmd_module._parse_agent_turn(response)

    assert turn is None
    assert error is not None
    assert "schedule_summary" in error
