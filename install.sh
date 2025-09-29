#!/bin/bash

# This script sets up the schedule management reminder system for macOS and Linux

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Script configuration
SCRIPT_NAME="Schedule Management Installer"
PYTHON_VERSION="3.12"
# VENV_NAME="schedule_management_env"
INSTALL_DIR="$HOME/SCHEDULE_MANAGEMENT"
LAUNCH_AGENT_NAME="com.sergiudm.schedule.management.reminder"
LAUNCH_AGENT_PLIST="$HOME/Library/LaunchAgents/${LAUNCH_AGENT_NAME}.plist"
SYSTEMD_SERVICE_NAME="schedule-management.service"
SYSTEMD_SERVICE_PATH="$HOME/.config/systemd/user/${SYSTEMD_SERVICE_NAME}"

# Detect OS
detect_os() {
    if [[ "$OSTYPE" == "darwin"* ]]; then
        echo "macos"
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        echo "linux"
    else
        echo "unknown"
    fi
}

OS_TYPE=$(detect_os)

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check OS compatibility
check_os() {
    if [[ "$OS_TYPE" == "unknown" ]]; then
        log_error "Unsupported operating system: $OSTYPE"
        log_info "Supported systems: macOS (darwin) and Linux (linux-gnu)"
        exit 1
    fi
    log_success "$OS_TYPE detected"
}

# Get Linux distribution info
get_linux_distro() {
    if [[ -f /etc/os-release ]]; then
        . /etc/os-release
        echo "$ID"
    else
        echo "unknown"
    fi
}

# Install package manager dependencies for Linux
install_linux_dependencies() {
    log_info "Installing Linux dependencies..."
    
    DISTRO=$(get_linux_distro)
    log_info "Detected Linux distribution: $DISTRO"
    
    case "$DISTRO" in
        ubuntu|debian)
            sudo apt update
            sudo apt install -y curl build-essential libssl-dev zlib1g-dev \
                libbz2-dev libreadline-dev libsqlite3-dev libncursesw5-dev \
                xz-utils tk-dev libxml2-dev libxmlsec1-dev libffi-dev liblzma-dev
            ;;
        fedora)
            sudo dnf install -y curl gcc zlib-devel bzip2 bzip2-devel \
                readline-devel sqlite sqlite-devel openssl-devel xz xz-devel \
                libffi-devel findutils
            ;;
        arch|manjaro)
            sudo pacman -S --needed curl base-devel openssl zlib xz
            ;;
        *)
            log_warning "Unknown distribution: $DISTRO. Please install dependencies manually:"
            log_info "Required: curl, build tools, Python development headers, OpenSSL"
            ;;
    esac
    
    log_success "Linux dependencies installed"
}

# Check if Homebrew is installed (macOS only)
check_homebrew() {
    if [[ "$OS_TYPE" != "macos" ]]; then
        return 0
    fi
    
    if ! command -v brew &> /dev/null; then
        log_warning "Homebrew not found. Installing Homebrew..."
        /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
        if [[ ":$PATH:" != *":/opt/homebrew/bin:"* ]]; then
            echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> ~/.zprofile
            eval "$(/opt/homebrew/bin/brew shellenv)"
        fi
    else
        log_success "Homebrew is already installed"
    fi
}

# Install uv package manager
install_uv() {
    log_info "Checking uv installation..."
    if ! command -v uv &> /dev/null; then
        log_info "uv not found. Installing uv..."
        
        if [[ "$OS_TYPE" == "macos" ]]; then
            brew install uv
        elif [[ "$OS_TYPE" == "linux" ]]; then
            # Install uv using the official installer
            curl -LsSf https://astral.sh/uv/install.sh | sh
            # Add to PATH
            export PATH="$HOME/.cargo/bin:$PATH"
            echo 'export PATH="$HOME/.cargo/bin:$PATH"' >> ~/.bashrc
        fi
        log_success "uv installed successfully"
    else
        log_success "uv is already installed"
    fi
    
    if ! uv --version &> /dev/null; then
        log_error "uv installation verification failed"
        exit 1
    fi
}

# Install Python (platform-specific)
install_python() {
    log_info "Setting up Python $PYTHON_VERSION..."
    
    if [[ "$OS_TYPE" == "macos" ]]; then
        # macOS: use pyenv
        if ! command -v pyenv &> /dev/null; then
            log_info "Installing pyenv..."
            brew install pyenv
            echo 'eval "$(pyenv init -)"' >> ~/.zshrc
            eval "$(pyenv init -)"
        fi
        if ! pyenv versions --bare | grep -q "^$PYTHON_VERSION$"; then
            log_info "Installing Python $PYTHON_VERSION..."
            pyenv install "$PYTHON_VERSION"
        fi
        pyenv local "$PYTHON_VERSION"
    elif [[ "$OS_TYPE" == "linux" ]]; then
        # Linux: use system Python or pyenv
        if command -v python3.$PYTHON_VERSION &> /dev/null; then
            log_success "Python $PYTHON_VERSION found in system"
        else
            log_info "Installing Python $PYTHON_VERSION using pyenv..."
            if ! command -v pyenv &> /dev/null; then
                curl https://pyenv.run | bash
                export PATH="$HOME/.pyenv/bin:$PATH"
                eval "$(pyenv init -)"
                echo 'export PATH="$HOME/.pyenv/bin:$PATH"' >> ~/.bashrc
                echo 'eval "$(pyenv init -)"' >> ~/.bashrc
            fi
            if ! pyenv versions --bare | grep -q "^$PYTHON_VERSION$"; then
                pyenv install "$PYTHON_VERSION"
            fi
            pyenv local "$PYTHON_VERSION"
        fi
    fi
    
    log_success "Python $PYTHON_VERSION is ready"
}

# Setup project directory (preserve src layout!)
setup_project() {
    log_info "Setting up project directory..."

    if [[ -d "$INSTALL_DIR" ]]; then
        log_warning "Installation directory exists. Backing up..."
        mv "$INSTALL_DIR" "${INSTALL_DIR}.backup.$(date +%Y%m%d_%H%M%S)"
    fi

    mkdir -p "$INSTALL_DIR"
    mkdir -p "$INSTALL_DIR/config"

    if [[ -d "src" ]]; then
        cp -r src "$INSTALL_DIR/"
        log_success "src/ directory copied (preserving layout)"
    else
        log_error "src/ directory not found in current working directory!"
        exit 1
    fi

    # Copy metadata files
    for file in pyproject.toml README.md uv.lock; do
        if [[ -f "$file" ]]; then
            cp "$file" "$INSTALL_DIR/"
            log_success "$file copied"
        fi
    done

    # Copy config files
    for config_file in settings.toml odd_weeks.toml even_weeks.toml; do
        if [[ -f "config/$config_file" ]]; then
            cp "config/$config_file" "$INSTALL_DIR/config/"
        fi
    done

    mkdir -p "$INSTALL_DIR/logs"
    log_success "Project directory setup complete"
}

# Create virtual environment
create_venv() {
    log_info "Creating virtual environment with uv..."
    uv venv --python=3.12 --clear "$INSTALL_DIR/.venv"
    if [[ -f "$INSTALL_DIR/.venv/bin/activate" ]]; then
        source "$INSTALL_DIR/.venv/bin/activate"
        log_success "Virtual environment created and activated with uv"
    else
        log_error "Virtual environment creation failed"
        exit 1
    fi
}

# Install dependencies and package
install_dependencies() {
    log_info "Installing dependencies and package..."

    cd "$INSTALL_DIR"

    # Upgrade pip
    uv pip install --upgrade pip

    # Install from requirements if available
    if [[ -f "../requirements.txt" ]]; then
        uv pip install -r ../requirements.txt
    fi
    if [[ -f "../requirements-test.txt" ]]; then
        uv pip install -r ../requirements-test.txt
    fi

    # Install editable package (supports src layout)
    uv pip install -e .
    if ! command -v reminder &> /dev/null; then
        log_warning "CLI 'reminder' not in PATH, but should work via venv"
    else
        log_success "CLI tool 'reminder' is available"
    fi

    cd - > /dev/null
}

# Create systemd service (Linux only)
create_systemd_service() {
    if [[ "$OS_TYPE" != "linux" ]]; then
        return 0
    fi
    
    log_info "Creating systemd service..."
    
    mkdir -p "$HOME/.config/systemd/user"
    
    cat > "$SYSTEMD_SERVICE_PATH" << EOF
[Unit]
Description=Schedule Management Reminder
After=graphical-session.target

[Service]
Type=simple
ExecStart=$INSTALL_DIR/.venv/bin/python $INSTALL_DIR/src/schedule_management/reminder_macos.py
Restart=always
RestartSec=10
Environment=DISPLAY=:0
Environment=REMINDER_CONFIG_DIR=$INSTALL_DIR/config
StandardOutput=$INSTALL_DIR/logs/schedule_management.out
StandardError=$INSTALL_DIR/logs/schedule_management.err

[Install]
WantedBy=default.target
EOF

    systemctl --user daemon-reload
    systemctl --user enable "$SYSTEMD_SERVICE_NAME"
    log_success "systemd service created and enabled"
}

# Create LaunchAgent plist (macOS only)
create_launch_agent() {
    if [[ "$OS_TYPE" != "macos" ]]; then
        return 0
    fi
    
    log_info "Creating LaunchAgent..."

    mkdir -p "$HOME/Library/LaunchAgents"

    cat > "$LAUNCH_AGENT_PLIST" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>${LAUNCH_AGENT_NAME}</string>
    <key>ProgramArguments</key>
    <array>
        <string>$INSTALL_DIR/.venv/bin/python</string>
        <string>$INSTALL_DIR/src/schedule_management/reminder_macos.py</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>$INSTALL_DIR/logs/schedule_management.out</string>
    <key>StandardErrorPath</key>
    <string>$INSTALL_DIR/logs/schedule_management.err</string>
    <key>WorkingDirectory</key>
    <string>$INSTALL_DIR</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>REMINDER_CONFIG_DIR</key>
        <string>$INSTALL_DIR/config</string>
    </dict>
</dict>
</plist>
EOF

    log_success "LaunchAgent created at $LAUNCH_AGENT_PLIST"
}

# Request permissions (platform-specific)
request_permissions() {
    if [[ "$OS_TYPE" == "macos" ]]; then
        log_info "The app will request Accessibility & Notification permissions on first run."
    elif [[ "$OS_TYPE" == "linux" ]]; then
        log_info "The app will use desktop notifications. Ensure notification daemon is running."
    fi
}

# Create convenience scripts (platform-specific)
create_scripts() {
    log_info "Creating convenience scripts..."

    # Start script (common)
    cat > "$INSTALL_DIR/start_reminders.sh" << EOF
#!/bin/bash
source "$INSTALL_DIR/.venv/bin/activate"
cd "$INSTALL_DIR/src/schedule_management"
exec python reminder_macos.py
EOF

    # Stop script (platform-specific)
    if [[ "$OS_TYPE" == "macos" ]]; then
        cat > "$INSTALL_DIR/stop_reminders.sh" << 'EOF'
#!/bin/bash
launchctl unload "$HOME/Library/LaunchAgents/com.sergiudm.schedule.management.reminder.plist" 2>/dev/null || true
pkill -f "python.*reminder_macos.py" 2>/dev/null || true
EOF
    elif [[ "$OS_TYPE" == "linux" ]]; then
        cat > "$INSTALL_DIR/stop_reminders.sh" << 'EOF'
#!/bin/bash
systemctl --user stop schedule-management.service 2>/dev/null || true
systemctl --user disable schedule-management.service 2>/dev/null || true
pkill -f "python.*reminder_macos.py" 2>/dev/null || true
EOF
    fi

    # Restart script (platform-specific)
    if [[ "$OS_TYPE" == "macos" ]]; then
        cat > "$INSTALL_DIR/restart_reminders.sh" << 'EOF'
#!/bin/bash
"$INSTALL_DIR/stop_reminders.sh"
sleep 2
launchctl load "$HOME/Library/LaunchAgents/com.sergiudm.schedule.management.reminder.plist"
EOF
    elif [[ "$OS_TYPE" == "linux" ]]; then
        cat > "$INSTALL_DIR/restart_reminders.sh" << 'EOF'
#!/bin/bash
"$INSTALL_DIR/stop_reminders.sh"
sleep 2
systemctl --user start schedule-management.service
EOF
    fi

    # Visualize script (common)
    cat > "$INSTALL_DIR/visualize_schedule.sh" << EOF
#!/bin/bash
source "$INSTALL_DIR/.venv/bin/activate"
cd "$INSTALL_DIR/src/schedule_management"
exec python reminder_macos.py --visualize
EOF

    # CLI wrapper (common)
    cat > "$INSTALL_DIR/reminder" << EOF
#!/bin/bash
source "$INSTALL_DIR/.venv/bin/activate"
exec reminder "\$@"
EOF

    chmod +x "$INSTALL_DIR"/*.sh "$INSTALL_DIR/reminder"
    log_success "Convenience scripts created"
}

# Test installation
test_installation() {
    log_info "Testing installation..."

    source "$INSTALL_DIR/.venv/bin/activate"

    if python -c "import schedule_management; print('OK')" &>/dev/null; then
        log_success "schedule_management import test passed"
    else
        log_error "Failed to import schedule_management"
        exit 1
    fi

    if reminder --help &>/dev/null; then
        log_success "CLI 'reminder' works correctly"
    else
        log_error "CLI 'reminder' failed"
        exit 1
    fi

    log_success "All tests passed"
}

# Display usage (platform-specific)
display_usage() {
    log_info "Installation completed successfully!"
    echo
    echo "=== Usage ==="
    echo "Add to PATH (optional):"
    if [[ "$OS_TYPE" == "macos" ]]; then
        echo "  echo 'export PATH=\"\$PATH:$INSTALL_DIR\"' >> ~/.zshrc"
    elif [[ "$OS_TYPE" == "linux" ]]; then
        echo "  echo 'export PATH=\"\$PATH:$INSTALL_DIR\"' >> ~/.bashrc"
    fi
    echo
    echo "Manual control:"
    echo "  $INSTALL_DIR/start_reminders.sh"
    echo "  $INSTALL_DIR/stop_reminders.sh"
    echo
    if [[ "$OS_TYPE" == "macos" ]]; then
        echo "LaunchAgent:"
        echo "  launchctl load $LAUNCH_AGENT_PLIST   # Enable auto-start"
        echo "  launchctl unload $LAUNCH_AGENT_PLIST # Disable"
    elif [[ "$OS_TYPE" == "linux" ]]; then
        echo "systemd service:"
        echo "  systemctl --user start $SYSTEMD_SERVICE_NAME   # Start service"
        echo "  systemctl --user stop $SYSTEMD_SERVICE_NAME    # Stop service"
        echo "  systemctl --user enable $SYSTEMD_SERVICE_NAME  # Enable auto-start"
        echo "  systemctl --user disable $SYSTEMD_SERVICE_NAME # Disable auto-start"
        echo "  systemctl --user status $SYSTEMD_SERVICE_NAME  # Check status"
    fi
    echo
    echo "Logs: $INSTALL_DIR/logs/"
    echo
    if [[ "$OS_TYPE" == "macos" ]]; then
        log_warning "First run will prompt for Accessibility permissions in System Settings."
    elif [[ "$OS_TYPE" == "linux" ]]; then
        log_info "First run will use desktop notifications. Ensure notification daemon is running."
    fi
}

# Cleanup
cleanup() {
    if [[ -n "${VIRTUAL_ENV:-}" ]]; then
        deactivate 2>/dev/null || true
    fi
}

# Main
main() {
    echo "=== $SCRIPT_NAME ==="
    trap cleanup EXIT

    check_os
    
    if [[ "$OS_TYPE" == "linux" ]]; then
        install_linux_dependencies
    fi
    
    check_homebrew
    install_uv
    # install_python
    setup_project
    create_venv
    install_dependencies
    
    if [[ "$OS_TYPE" == "macos" ]]; then
        create_launch_agent
    elif [[ "$OS_TYPE" == "linux" ]]; then
        create_systemd_service
    fi
    
    request_permissions
    create_scripts
    test_installation
    display_usage

    log_success "Installation complete! 🎉"
}

# Parse args (minimal)
while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            echo "Usage: $0"
            exit 0
            ;;
        *)
            log_error "Unknown option: $1"
            exit 1
            ;;
    esac
done

main