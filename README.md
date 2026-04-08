# Schedule Everything

[![Logic Tests](https://github.com/sergiudm/schedule-everything/actions/workflows/logic-tests.yml/badge.svg)](https://github.com/sergiudm/schedule-everything/actions/workflows/logic-tests.yml)
[![CLI Tests](https://github.com/sergiudm/schedule-everything/actions/workflows/cli-tests.yml/badge.svg)](https://github.com/sergiudm/schedule-everything/actions/workflows/cli-tests.yml)
[![PyPI version](https://badge.fury.io/py/schedule-management.svg)](https://pypi.org/project/schedule-management)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)
[![Documentation](https://img.shields.io/badge/docs-GitHub_Pages-blue)](https://sergiudm.github.io/schedule-everything/)
[![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/sergiudm/schedule-everything)
[中文版本](README_zh.md)

AI-assisted time management for people who want a schedule that is easy to use,
local-first, and grounded in healthier defaults instead of pure calendar spam.

`reminder setup` is profile-first: it creates or refines `profile.md`, asks
follow-up questions, summarizes the plan, and only then writes the schedule.
`reminder sync` takes your current tasks and turns today's pomodoro/potato
blocks into concrete work items with a preview-before-save loop.

## Why This Exists

Most productivity tools are good at filling time and bad at protecting energy.
Schedule Everything is built around a different assumption: good time
management should be easier, more personalized, and more scientifically
informed.

When your preferences are incomplete, the planner leans on evidence-informed
defaults that try to protect:

- enough sleep opportunity instead of routinely cutting sleep for more work
- regular sleep timing instead of large weekday/weekend swings
- consistent movement and exercise across the week
- short recovery breaks during long desk-bound stretches
- earlier placement of demanding work when daylight and flexibility allow

These are heuristics, not medical advice. Real constraints, clinician guidance,
shift work, disability needs, and caregiving realities should override them.

Selected sources:

- Watson NF, Badr MS, Belenky G, et al. Recommended Amount of Sleep for a Healthy Adult. [AASM consensus PDF](https://aasm.org/resources/pdf/pressroom/adult-sleep-duration-consensus.pdf)
- Sletten TL, Weaver MD, Foster RG, et al. The importance of sleep regularity. [Sleep Health, 2023](https://doi.org/10.1016/j.sleh.2023.07.016)
- World Health Organization. Physical activity recommendations for adults. [WHO guidance](https://www.who.int/initiatives/behealthy/physical-activity)
- Albulescu P, Macsinga I, Rusu A, et al. "Give me a break!" [PLOS ONE, 2022](https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0272460)
- Figueiro MG, Steverson B, Heerwagen J, et al. The impact of daytime light exposures on sleep and mood in office workers. [Sleep Health, 2017](https://doi.org/10.1016/j.sleh.2017.03.005)

## Why It Feels Easy

- `profile.md` stores durable context about how you work, not just what time blocks exist.
- `reminder setup` asks normal-language questions instead of forcing you to hand-author a calendar first.
- `reminder sync` converts `tasks.json` into titled focus blocks and asks for approval before writing anything.
- The system stays local: TOML files, JSON task data, and a small CLI instead of a cloud dashboard.
- You can still inspect and edit everything manually because the generated files are plain text.

## Quick Start

### 1. Install

```bash
git clone --recurse-submodules https://github.com/sergiudm/schedule-everything.git
cd schedule-everything
./install.sh
./third_party/opencode/install --no-modify-path
```

### 2. Build Your Schedule with AI

```bash
reminder setup
```

This stores model settings in `~/.schedule_management/llm.toml`, builds or
updates `profile.md`, and generates your schedule only after showing you a
summary first.

### 3. Add Tasks and Sync Today

```bash
reminder add "Finish proposal draft" 9
reminder add "Review PR #128" 7
reminder sync
```

`reminder sync` reads `tasks/tasks.json`, proposes task assignments for today's
pomodoro/potato blocks, and regenerates if you reject the preview with
feedback.

### 4. Check the Result

```bash
reminder status
reminder status -v
reminder view
reminder update
```

When a sync overlay exists for today, `reminder status` shows the block type and
the specific assigned event, for example `pomodoro: Finish proposal draft`.

## Core Commands

| Command | What it does |
| --- | --- |
| `reminder setup` | Build or modify your schedule with a profile-first AI workflow |
| `reminder sync` | Assign today's pomodoro/potato blocks to tasks with preview + approval |
| `reminder status [-v]` | Show what is happening now and today's schedule, including synced titles |
| `reminder add/ls/rm` | Manage the task list that feeds the sync flow |
| `reminder track` | Record habits |
| `reminder ddl` | Manage deadlines |
| `reminder view` | Generate a PDF schedule visualization |

## Manual Setup and Docs

The low-level manual configuration flow has been moved to the docs.

- [Introduction](https://sergiudm.github.io/schedule-everything/docs/intro)
- [Quick Start](https://sergiudm.github.io/schedule-everything/docs/quick-start)
- [Installation](https://sergiudm.github.io/schedule-everything/docs/installation)
- [Configuration Overview](https://sergiudm.github.io/schedule-everything/docs/configuration/overview)
- [CLI Overview](https://sergiudm.github.io/schedule-everything/docs/cli/overview)

## License

Distributed under the **MIT License**. See [LICENSE](LICENSE).
