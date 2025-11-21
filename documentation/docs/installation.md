---
sidebar_position: 2
---

# Installation

This guide details how to install and configure Schedule Management on your system.

> **Compatibility Note**: This tool is currently optimized for **macOS** (via `launchd`) and **Linux**. Windows support is on the roadmap.

## Prerequisites

Before proceeding, ensure you have the following installed:

*   **Python 3.12+**: [Download Python](https://www.python.org/downloads/)
*   **Git**: [Download Git](https://git-scm.com/downloads)
*   **Terminal**: Any standard terminal emulator (Terminal.app, iTerm2, etc.)

## Installation Methods

We provide an automated installer for convenience, but manual installation is fully supported for users who prefer granular control.

### Method 1: Automated Installer (Recommended)

The `install.sh` script handles dependency installation, configuration scaffolding, and service registration in one go.

1.  **Clone the repository**:
    ```bash
    git clone https://github.com/sergiudm/schedule_management.git
    cd schedule_management
    ```

2.  **Run the installer**:
    ```bash
    ./install.sh
    ```

    The script will:
    *   Install the Python package and dependencies.
    *   Create the `~/schedule_management` directory structure.
    *   Copy default configuration templates.
    *   Register the background service (on macOS).

3.  **Finalize Setup**:
    Follow the on-screen instructions to load the service. Typically, this involves:
    ```bash
    launchctl load ~/Library/LaunchAgents/com.sergiudm.schedule_management.plist
    ```

### Method 2: Manual Installation

For advanced users or those integrating into existing environments.

1.  **Clone the repository**:
    ```bash
    git clone https://github.com/sergiudm/schedule_management.git
    cd schedule_management
    ```

2.  **Install the Package**:
    We recommend installing in editable mode (`-e`) to easily pull updates.
    ```bash
    pip install -e .
    ```
    *Tip: Consider using a virtual environment (`venv` or `conda`) to isolate dependencies.*

3.  **Create Configuration Directory**:
    ```bash
    mkdir -p ~/schedule_management/config
    ```

4.  **Initialize Config Files**:
    Copy the templates to your config directory:
    ```bash
    cp config/settings_template.toml ~/schedule_management/config/settings.toml
    cp config/week_schedule_template.toml ~/schedule_management/config/odd_weeks.toml
    cp config/week_schedule_template.toml ~/schedule_management/config/even_weeks.toml
    ```

5.  **Configure Shell Environment**:
    Add the following to your shell profile (`~/.zshrc`, `~/.bash_profile`, etc.) to access the `reminder` CLI:

    ```bash
    export PATH="$HOME/schedule_management:$PATH"
    export REMINDER_CONFIG_DIR="$HOME/schedule_management/config"
    alias reminder="$HOME/schedule_management/reminder"
    ```

6.  **Apply Changes**:
    ```bash
    source ~/.zshrc  # or your specific profile file
    ```

### Method 3: PyPI Installation

*Note: This method installs the library code but requires manual configuration setup.*

```bash
pip install schedule-management
```
After installation, follow steps 3-6 from the "Manual Installation" section above.

## Verifying Installation

Confirm that everything is working correctly.

1.  **Check CLI**:
    ```bash
    reminder --help
    ```
    *Expected output: A list of available commands.*

2.  **Check Service Status** (macOS):
    ```bash
    launchctl list | grep schedule
    ```
    *Expected output: A process ID and status code (usually 0).*

3.  **View Schedule**:
    ```bash
    reminder status
    ```
    *Expected output: A summary of upcoming events or "No upcoming events".*

## Uninstallation

To completely remove the application:

1.  **Unload the Service**:
    ```bash
    launchctl unload ~/Library/LaunchAgents/com.sergiudm.schedule_management.plist
    ```

2.  **Remove Configuration & Data**:
    ```bash
    rm -rf "$HOME/schedule_management"
    ```

3.  **Remove Python Package**:
    ```bash
    pip uninstall schedule-management
    ```

## Troubleshooting

*   **"Command not found: reminder"**: Ensure you have added the alias and exports to your shell profile and sourced it.
*   **Service not starting**: Check the logs (standard error/output) or try running `reminder update` to refresh the service definition.
