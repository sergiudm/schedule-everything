# Schedule Everything

[![Logic Tests](https://github.com/sergiudm/schedule-everything/actions/workflows/logic-tests.yml/badge.svg)](https://github.com/sergiudm/schedule-everything/actions/workflows/logic-tests.yml)
[![CLI Tests](https://github.com/sergiudm/schedule-everything/actions/workflows/cli-tests.yml/badge.svg)](https://github.com/sergiudm/schedule-everything/actions/workflows/cli-tests.yml)
[![PyPI version](https://badge.fury.io/py/schedule-management.svg)](https://pypi.org/project/schedule-management)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)
[![Documentation](https://img.shields.io/badge/docs-GitHub_Pages-blue)](https://sergiudm.github.io/schedule-everything/)
[![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/sergiudm/schedule-everything)
[中文版本](README_zh.md)

A simple, persistent way to manage your daily schedule.

`reminder setup` now uses a profile-first planning flow: it builds or refines a
`profile.md` file in the same directory as `settings.toml`, asks follow-up
questions until that profile is complete enough to drive scheduling decisions,
and only then generates schedule files.

<table>
  <tr>
    <td>
      <img src="assets/rmd_add.gif" alt="Add Schedule" width="100%">
    </td>
    <td>
      <img src="assets/rmd_view.gif" alt="View Schedule" width="100%">
    </td>
    <td>
      <img src="assets/rmd_alert.gif" alt="Alert Example" width="100%">
    </td>
    <td>
      <img src="assets/emergency.png" alt="Alert Example" width="100%">
    </td>
  </tr>
</table>

## ✨ Features

- **TOML Configuration**: Schedules are defined in clean, human-readable, and version-control friendly TOML files.
- **Dual Alerts**: Persistent notifications (modal dialogs) + audible sounds ensure you never miss a reminder.
- **Smart Rotation**: Automatically switches between **odd-week** and **even-week** schedules.
- **Flexible Events**: Supports time blocks (e.g., Pomodoro), specific time points, and recurring daily routines.
- **CLI Suite**: Integrated tools for managing tasks, tracking habits, and monitoring deadlines.
- **AI-Ready**: Easily generate configurations using LLMs from any text description.

## Evidence-Informed Healthy Scheduling

The setup assistant uses general, evidence-informed defaults when the user has
not specified a preference yet. In practice that means it tries to protect:

- sufficient sleep opportunity instead of routinely compressing sleep to fit more work
- regular sleep timing instead of large weekday/weekend swings
- consistent weekly movement and exercise
- short recovery or movement breaks during long sedentary work stretches
- daytime light exposure and earlier deep-work placement when the user has flexibility

These are population-level scheduling heuristics, not medical advice. If a user
has clinician guidance, disability needs, shift-work demands, caregiving
constraints, or other hard realities, those constraints should override the
defaults.

Relevant papers and guidelines:

- Watson NF, Badr MS, Belenky G, et al. Recommended Amount of Sleep for a Healthy Adult: A Joint Consensus Statement of the American Academy of Sleep Medicine and Sleep Research Society. [AASM consensus PDF](https://aasm.org/resources/pdf/pressroom/adult-sleep-duration-consensus.pdf) and [AASM advisory](https://aasm.org/advocacy/position-statements/adult-sleep-duration-health-advisory/)
- Sletten TL, Weaver MD, Foster RG, et al. The importance of sleep regularity: a consensus statement of the National Sleep Foundation sleep timing and variability panel. [Sleep Health, 2023](https://doi.org/10.1016/j.sleh.2023.07.016)
- World Health Organization. Physical activity recommendations for adults. [WHO guidance](https://www.who.int/initiatives/behealthy/physical-activity)
- Albulescu P, Macsinga I, Rusu A, et al. "Give me a break!" A systematic review and meta-analysis on the efficacy of micro-breaks for increasing well-being and performance. [PLOS ONE, 2022](https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0272460)
- Figueiro MG, Steverson B, Heerwagen J, et al. The impact of daytime light exposures on sleep and mood in office workers. [Sleep Health, 2017](https://doi.org/10.1016/j.sleh.2017.03.005)

---

## 🚀 Quickstart

### 1. Install
```bash
git clone --recurse-submodules https://github.com/sergiudm/schedule-everything.git
cd schedule-everything
./install.sh
```

Install OpenCode CLI from the bundled submodule (required by `reminder setup` and `reminder sync`):

```bash
./third_party/opencode/install --no-modify-path
```

### 2. Build Your Schedule with AI Assistance
```bash
reminder setup
```
This command will guide you through configuring model credentials and interactively building or modifying your schedules.
The setup agent is powered by OpenCode (`opencode run`) and can attach your timetable files directly.

After you add tasks, generate today's titled focus blocks with:

```bash
reminder sync
```

---

## 🛠️ Manual Setup

### 1. Setup Configuration
Copy the templates to create your configuration files in `config/`:

```bash
cp config/settings_template.toml config/settings.toml
cp config/week_schedule_template.toml config/odd_weeks.toml
cp config/week_schedule_template.toml config/even_weeks.toml
```

### 2. Edit Configs
Define your routine in `config/`.
- **`settings.toml`**: Global settings and reusable time blocks (e.g., `pomodoro = 25`).
- **`odd_weeks.toml` / `even_weeks.toml`**: Your daily schedules.
- **`synced_schedule.toml`**: An accepted daily overlay generated by `reminder sync` for today's pomodoro/potato task assignments.

**Example Schedule Entry:**
```toml
[monday]
"09:00" = "pomodoro"                              # Reusable block (start + end alert)
"14:00" = { block = "meeting", title = "Sync" }   # Block with custom title
"22:00" = "Go to sleep 😴"                        # Simple time point alert
```

> [!TIP]
> Use [our prompts](docs/prompt) to generate these configs instantly using an AI model.

### 3. Install
Run the installer to set up the background service:

```bash
./install.sh
```
During installation, existing config is checked and any missing required values are prompted one by one.
*Follow the output instructions to load the launchd agent if required.*

### 4. Optional: Interactive AI Setup
Use the new setup wizard to configure model credentials and build/modify schedules interactively:

```bash
reminder setup
```

The wizard stores model settings in `~/.schedule_management/llm.toml`, checks whether a complete local schedule config already exists, and then guides you to build or modify schedules through OpenCode.
In build mode, it first reads or creates `profile.md` in the same config directory as `settings.toml`, asks iterative follow-up questions until that profile is complete, generates a pure-text schedule summary for confirmation, and only then writes TOML configuration files.
In modify mode, it reads `profile.md` first so schedule edits stay aligned with the user's long-term context.
During build/modify turns, the OpenCode-backed agent can attach local files/images and use built-in tooling to reason over project/context files when needed.
When the user leaves details open, the planner falls back to evidence-informed heuristics around sleep regularity, physical activity, movement breaks, and daytime light exposure.

---

## 🛠️ CLI Reference

Add the following to your shell profile (e.g., `~/.zshrc`) to use the `reminder` command:

```bash
export PATH="$HOME/schedule_management:$PATH"
export REMINDER_CONFIG_DIR="$HOME/schedule_management/config"
alias reminder="$HOME/schedule_management/reminder"
```

### Command Overview

| Category      | Command                           | Description                                  |
| ------------- | --------------------------------- | -------------------------------------------- |
| **System**    | `reminder update`                 | Reload config and restart background service |
|               | `reminder setup`                  | Interactive AI setup powered by OpenCode with profile-first intake, evidence-informed planning, summary confirmation, build/modify flows, and optional file-aware reasoning |
|               | `reminder sync`                   | Generate and confirm today's pomodoro/potato task assignments with an LLM |
|               | `reminder status [-v]`            | Show upcoming events (or full schedule), including synced task titles when available |
|               | `reminder view`                   | Generate and view a PDF schedule visualization |
|               | `reminder edit <file>`            | Edit a config file directly                  |
|               | `reminder stop`                   | Stop the alarm service                       |
| **Tasks**     | `reminder add "task" <1-10>`      | Add/update task with importance level        |
|               | `reminder ls`                     | List tasks by importance                     |
|               | `reminder rm "task"` / `rm <id>`  | Remove task by name or ID                    |
| **Deadlines** | `reminder ddl`                    | Show deadlines with urgency status           |
|               | `reminder ddl add "name" "MM.DD"` | Add or update a deadline                     |
|               | `reminder ddl rm <events...>`     | Remove one or more deadlines                 |
| **Habits**    | `reminder track [ids...]`         | Log completed habits for today (opens a prompt if no IDs) |
| **Reports**   | `reminder report <type>`          | Generate weekly or monthly PDF reports       |

> For detailed usage, refer to the [CLI Overview](https://sergiudm.github.io/schedule-everything/docs/cli/overview).

### Usage Examples

```bash
# Add a high-priority task
reminder add "Finish Report" 9

# Generate today's task assignments for focus blocks
reminder sync

# Add a deadline for Dec 25th
reminder ddl add "Project Launch" "12.25"

# Track habits 1 and 2 as done for today
reminder track 1 2

# Or use the prompt window (no IDs)
reminder track

# Launch interactive setup/build wizard
reminder setup
```

Habit prompts can also be scheduled automatically via `config/settings.toml` (`[tasks].habit_prompt = "HH:MM"`).

---

## 🗺️ Roadmap

- [x] Time point alarms
- [x] Default schedule templates
- [x] Schedule visualization
- [x] Installation script
- [x] Skip-day logic 
- [x] CLI tool
- [x] Task management system with importance levels
- [x] Deadline management system
- [x] Habit tracking system
- [x] Prompts for LLMs to create TOML configs
- [x] Daily summary before bedtime
- [x] Today's tasks overview
- [x] Self rewarding system
- [x] History analysis and weekly reports
- [ ] Multi-language support
- [ ] Website for schedule sharing
- [ ] Better alarm UI
- [ ] **Windows support**

---

## 📄 License

Distributed under the **MIT License**. See [LICENSE](LICENSE).
