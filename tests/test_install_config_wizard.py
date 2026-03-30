import tomllib

from schedule_management.install_config_wizard import run_wizard


def _write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_run_wizard_creates_required_files(tmp_path):
    config_dir = tmp_path / "config"
    template_dir = tmp_path / "templates"

    _write(
        template_dir / "settings_template.toml",
        """
[settings]
sound_file = "/tmp/ping.aiff"
alarm_interval = 5

[paths]
reports_path = "~/Desktop/reports"
""".strip()
        + "\n",
    )
    _write(
        template_dir / "week_schedule_template.toml",
        """
[monday]
"09:00" = "pomodoro"
""".strip()
        + "\n",
    )
    _write(
        template_dir / "habits_template.toml",
        """
[habits]
1 = "Read"
""".strip()
        + "\n",
    )

    success = run_wizard(config_dir, template_dir, auto_yes=True)

    assert success
    assert (config_dir / "settings.toml").exists()
    assert (config_dir / "odd_weeks.toml").exists()
    assert (config_dir / "even_weeks.toml").exists()
    assert (config_dir / "habits.toml").exists()


def test_run_wizard_prompts_for_missing_settings(tmp_path):
    config_dir = tmp_path / "config"
    template_dir = tmp_path / "templates"

    _write(
        config_dir / "settings.toml",
        """
[settings]
sound_file = "/tmp/ping.aiff"
""".strip()
        + "\n",
    )
    _write(config_dir / "odd_weeks.toml", '[monday]\n"09:00" = "pomodoro"\n')
    _write(config_dir / "even_weeks.toml", '[monday]\n"09:00" = "pomodoro"\n')
    _write(config_dir / "habits.toml", '[habits]\n1 = "Read"\n')

    _write(
        template_dir / "settings_template.toml",
        """
[settings]
sound_file = "/tmp/ping.aiff"
alarm_interval = 5

[paths]
reports_path = "~/Desktop/reports"
""".strip()
        + "\n",
    )
    _write(
        template_dir / "week_schedule_template.toml",
        """
[monday]
"09:00" = "pomodoro"
""".strip()
        + "\n",
    )
    _write(
        template_dir / "habits_template.toml",
        """
[habits]
1 = "Read"
""".strip()
        + "\n",
    )

    responses = iter(["7", "~/Desktop/custom-reports"])
    success = run_wizard(
        config_dir,
        template_dir,
        auto_yes=False,
        input_func=lambda _: next(responses),
    )

    assert success

    with open(config_dir / "settings.toml", "rb") as handle:
        data = tomllib.load(handle)

    assert data["settings"]["alarm_interval"] == 7
    assert data["paths"]["reports_path"] == "~/Desktop/custom-reports"


def test_run_wizard_aborts_when_required_file_creation_declined(tmp_path):
    config_dir = tmp_path / "config"
    template_dir = tmp_path / "templates"

    _write(
        template_dir / "settings_template.toml",
        """
[settings]
sound_file = "/tmp/ping.aiff"
""".strip()
        + "\n",
    )
    _write(template_dir / "week_schedule_template.toml", "[monday]\n")
    _write(template_dir / "habits_template.toml", '[habits]\n1 = "Read"\n')

    responses = iter(["n"])
    success = run_wizard(
        config_dir,
        template_dir,
        auto_yes=False,
        input_func=lambda _: next(responses),
    )

    assert not success
    assert not (config_dir / "settings.toml").exists()
