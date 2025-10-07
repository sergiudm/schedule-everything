---
sidebar_position: 2
---

# Installation

This guide will help you install Schedule Management on your system. The tool is currently optimized for **macOS and Linux**, with Windows support planned for future releases.

## Prerequisites

- Python 3.12 or higher
- pip (Python package installer)
- Git (for cloning the repository)

## Installation Methods

### Method 1: Using the Installation Script (Recommended)

The easiest way to install Schedule Management is using the provided installation script:

```bash
# Clone the repository
git clone https://github.com/sergiudm/schedule_management.git
cd schedule_management

# Run the installation script
./install.sh
```

The installation script will:
- Install the Python package and its dependencies
- Set up the configuration directory
- Create the launchd service for auto-start (macOS)
- Configure the CLI tool

> **Note**: You may need to run `launchctl load ~/Library/LaunchAgents/com.sergiudm.schedule_management.plist` according to the script output. Then run `launchctl list | grep schedule` to check if the service is running.

### Method 2: Manual Installation

If you prefer to install manually or need more control over the process:

1. **Clone the repository**:
   ```bash
   git clone https://github.com/sergiudm/schedule_management.git
   cd schedule_management
   ```

2. **Install the Python package**:
   ```bash
   pip install -e .
   ```

3. **Set up the configuration directory**:
   ```bash
   mkdir -p ~/schedule_management/config
   cp config/settings_template.toml ~/schedule_management/config/settings.toml
   cp config/week_schedule_template.toml ~/schedule_management/config/odd_weeks.toml
   cp config/week_schedule_template.toml ~/schedule_management/config/even_weeks.toml
   ```

4. **Configure your shell profile**:
   Add these lines to `~/.zshrc` or `~/.bash_profile`:
   ```bash
   export PATH="$HOME/schedule_management:$PATH"
   export REMINDER_CONFIG_DIR="$HOME/schedule_management/config"
   alias reminder="$HOME/schedule_management/reminder"
   ```

5. **Reload your shell**:
   ```bash
   source ~/.zshrc  # or source ~/.bash_profile
   ```

### Method 3: Install from PyPI

You can also install directly from PyPI:

```bash
pip install schedule-management
```

After installation, you'll need to manually set up the configuration files and directories as described in the manual installation steps above.

## Verification

To verify that Schedule Management is installed correctly:

1. **Check the CLI tool**:
   ```bash
   reminder --help
   ```

2. **Check the service status** (if using auto-start):
   ```bash
   launchctl list | grep schedule
   ```

3. **Test the configuration**:
   ```bash
   reminder status
   ```

## Uninstallation

To uninstall Schedule Management:

```bash
# Stop the service (if running)
launchctl unload ~/Library/LaunchAgents/com.sergiudm.schedule_management.plist

# Remove the installation directory
rm -rf "$HOME/schedule_management"

# Uninstall the Python package
pip uninstall schedule-management
```

## Next Steps

Once installed, you can proceed to the [Quick Start Guide](quick-start.md) to configure your first schedule, or explore the [Configuration Reference](configuration/overview.md) for detailed setup options.