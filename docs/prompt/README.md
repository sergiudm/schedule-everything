# Schedule Configuration Prompts

This directory contains AI prompts to help you generate TOML configuration files for your schedule management system quickly and accurately.

## Available Prompts

- **[English Prompt](config_gen_prompt_en.md)** - Generate configuration in English
- **[中文提示](config_gen_prompt_zh.md)** - 用中文生成配置文件

## How to Use

1. Choose the appropriate prompt file for your language
2. Copy the prompt content to your preferred AI assistant (ChatGPT, Claude, etc.)
3. Describe your daily routine or paste your existing schedule
4. The AI will generate ready-to-use TOML configuration files
5. Save the generated content to your `config/` directory

## What Gets Generated

The prompts will help you create:
- `settings.toml` - Global settings, time blocks, and messages
- `odd_weeks.toml` - Schedule for odd-numbered weeks
- `even_weeks.toml` - Schedule for even-numbered weeks

## Tips for Best Results

- Be specific about your time preferences
- Mention any recurring patterns (daily, weekly)
- Include break preferences and work session lengths
- Specify any custom messages you'd like for reminders
- Indicate if you have different routines for different weeks

## Example Input

"I work from 9 AM to 6 PM with 25-minute Pomodoro sessions, 5-minute breaks, and a 1-hour lunch at noon. I want to go to bed at 10:30 PM and have a summary reminder at 9 PM."

## Example Output

The AI will generate complete TOML files with proper formatting and structure that you can directly use with the schedule management system.