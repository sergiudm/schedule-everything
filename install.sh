#!/bin/bash

# Awesome Healthy Habits - macOS Installation Script
# This script sets up the schedule management reminder system for macOS

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Script configuration
SCRIPT_NAME="Awesome Healthy Habits Installer"
PYTHON_VERSION="3.12"
VENV_NAME="healthy_habits_env"
INSTALL_DIR="$HOME/healthy_habits"
LAUNCH_AGENT_NAME="com.health.habits.reminder"
LAUNCH_AGENT_PLIST="$HOME/Library/LaunchAgents/${LAUNCH_AGENT_NAME}.plist"

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

# Check if running on macOS
check_macos() {
    if [[ "$OSTYPE" != "darwin"* ]]; then
        log_error "This script is designed for macOS only. Detected OS: $OSTYPE"
        exit 1
    fi
    log_success "macOS detected"
}

# Check if Homebrew is installed
check_homebrew() {
    if ! command -v brew &> /dev/null; then
        log_warning "Homebrew not found. Installing Homebrew..."
        /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
        
        # Add Homebrew to PATH if not already there
        if [[ ":$PATH:" != *":/opt/homebrew/bin:"* ]]; then
            echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> ~/.zprofile
            eval "$(/opt/homebrew/bin/brew shellenv)"
        fi
    else
        log_success "Homebrew is already installed"
    fi
}

# Check if uv is installed and install if necessary
check_uv() {
    log_info "Checking uv installation..."
    
    if ! command -v uv &> /dev/null; then
        log_info "uv not found. Installing uv via Homebrew..."
        brew install uv
        log_success "uv installed successfully"
    else
        log_success "uv is already installed"
    fi
    
    # Verify uv is working
    if uv --version &> /dev/null; then
        log_success "uv is working correctly"
    else
        log_error "uv installation verification failed"
        exit 1
    fi
}

# Install Python using pyenv
install_python() {
    log_info "Setting up Python $PYTHON_VERSION..."
    
    # Install pyenv if not already installed
    if ! command -v pyenv &> /dev/null; then
        log_info "Installing pyenv..."
        brew install pyenv
        echo 'eval "$(pyenv init -)"' >> ~/.zshrc
        eval "$(pyenv init -)"
    fi
    
    # Install Python version if not already installed
    if ! pyenv versions | grep -q "$PYTHON_VERSION"; then
        log_info "Installing Python $PYTHON_VERSION..."
        pyenv install $PYTHON_VERSION
    else
        log_info "Python $PYTHON_VERSION is already installed"
    fi
    
    # Set local Python version
    pyenv local $PYTHON_VERSION
    log_success "Python $PYTHON_VERSION is ready"
}

# Create virtual environment
create_venv() {
    log_info "Creating virtual environment..."
    
    if [[ -d "$INSTALL_DIR/$VENV_NAME" ]]; then
        log_warning "Virtual environment already exists. Removing old environment..."
        rm -rf "$INSTALL_DIR/$VENV_NAME"
    fi
    
    log_info "Creating venv at: $INSTALL_DIR/$VENV_NAME"
    python$PYTHON_VERSION -m venv "$INSTALL_DIR/$VENV_NAME"
    
    if [[ -f "$INSTALL_DIR/$VENV_NAME/bin/activate" ]]; then
        source "$INSTALL_DIR/$VENV_NAME/bin/activate"
        log_success "Virtual environment created and activated"
    else
        log_error "Virtual environment creation failed - activation script not found"
        exit 1
    fi
}

# Install Python dependencies
install_dependencies() {
    log_info "Installing Python dependencies..."
    
    # Change to installation directory for package installation
    cd "$INSTALL_DIR"
    
    # Upgrade pip first using uv
    uv pip install --upgrade pip
    
    # Install requirements from requirements.txt if it exists in the original location
    if [[ -f "../requirements.txt" ]]; then
        uv pip install -r ../requirements.txt
        log_success "Dependencies installed from requirements.txt"
    else
        log_warning "requirements.txt not found, installing matplotlib manually..."
        uv pip install matplotlib>=3.5.0
    fi
    
    # Install additional development dependencies if available
    if [[ -f "../requirements-test.txt" ]]; then
        uv pip install -r ../requirements-test.txt
        log_success "Test dependencies installed"
    fi
    
    # Install the local schedule-management package in editable mode
    log_info "Installing schedule-management package..."
    uv pip install -e .
    if [[ $? -eq 0 ]]; then
        log_success "Schedule-management package installed successfully"
    else
        log_error "Failed to install schedule-management package"
        exit 1
    fi
    
    # Verify the reminder command is available
    if command -v reminder &> /dev/null; then
        log_success "CLI tool 'reminder' is available"
    else
        log_warning "CLI tool 'reminder' may not be in PATH, but should be available in virtual environment"
    fi
    
    # Return to original directory
    cd - > /dev/null
}

# Setup project directory
setup_project() {
    log_info "Setting up project directory..."
    
    if [[ -d "$INSTALL_DIR" ]]; then
        log_warning "Installation directory already exists. Backing up..."
        mv "$INSTALL_DIR" "${INSTALL_DIR}.backup.$(date +%Y%m%d_%H%M%S)"
    fi
    
    mkdir -p "$INSTALL_DIR"
    mkdir -p "$INSTALL_DIR/config"
    
    # Copy project files
    if [[ -d "src/schedule_management" ]]; then
        cp -r src/schedule_management "$INSTALL_DIR/"
        log_success "Schedule management files copied"
    else
        log_error "src/schedule_management directory not found!"
        exit 1
    fi
    
    # Copy package configuration files for proper installation
    if [[ -f "pyproject.toml" ]]; then
        cp "pyproject.toml" "$INSTALL_DIR/"
        log_success "Package configuration (pyproject.toml) copied"
    else
        log_error "pyproject.toml not found!"
        exit 1
    fi
    
    if [[ -f "README.md" ]]; then
        cp "README.md" "$INSTALL_DIR/"
        log_success "README.md copied"
    fi
    
    if [[ -f "uv.lock" ]]; then
        cp "uv.lock" "$INSTALL_DIR/"
        log_success "uv.lock copied"
    fi
    
    # Copy configuration files if they exist
    for config_file in settings.toml odd_weeks.toml even_weeks.toml; do
        if [[ -f "config/$config_file" ]]; then
            cp "config/$config_file" "$INSTALL_DIR/config/"
        fi
    done
    
    # Create logs directory
    mkdir -p "$INSTALL_DIR/logs"
    
    log_success "Project directory setup complete"
}

# Create LaunchAgent for automatic startup
create_launch_agent() {
    log_info "Creating LaunchAgent for automatic startup..."
    
    # Create LaunchAgents directory if it doesn't exist
    mkdir -p "$HOME/Library/LaunchAgents"
    
    # Create plist file
    cat > "$LAUNCH_AGENT_PLIST" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>${LAUNCH_AGENT_NAME}</string>
    <key>ProgramArguments</key>
    <array>
        <string>$INSTALL_DIR/$VENV_NAME/bin/python</string>
        <string>$INSTALL_DIR/schedule_management/reminder_macos.py</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>$INSTALL_DIR/logs/healthy_habits.out</string>
    <key>StandardErrorPath</key>
    <string>$INSTALL_DIR/logs/healthy_habits.err</string>
    <key>WorkingDirectory</key>
    <string>$INSTALL_DIR/schedule_management</string>
</dict>
</plist>
EOF
    
    log_success "LaunchAgent created at $LAUNCH_AGENT_PLIST"
}

# Request necessary permissions
request_permissions() {
    log_info "Requesting necessary permissions..."
    
    # Check if we need to request accessibility permissions
    log_info "The reminder system will need accessibility permissions to show dialogs."
    log_info "You may be prompted to grant these permissions when the app first runs."
    
    # Check if we need to request notification permissions
    log_info "Notification permissions may also be required for the reminder system."
}

# Create convenience scripts
create_scripts() {
    log_info "Creating convenience scripts..."
    
    # Create start script
    cat > "$INSTALL_DIR/start_reminders.sh" << EOF
#!/bin/bash
source "$INSTALL_DIR/$VENV_NAME/bin/activate"
cd "$INSTALL_DIR/schedule_management"
python reminder_macos.py
EOF
    
    # Create stop script
    cat > "$INSTALL_DIR/stop_reminders.sh" << 'EOF'
#!/bin/bash
launchctl unload "$HOME/Library/LaunchAgents/com.health.habits.reminder.plist"
pkill -f "python.*reminder_macos.py"
EOF
    
    # Create restart script
    cat > "$INSTALL_DIR/restart_reminders.sh" << 'EOF'
#!/bin/bash
"$HOME/healthy_habits/stop_reminders.sh"
sleep 2
launchctl load "$HOME/Library/LaunchAgents/com.health.habits.reminder.plist"
EOF
    
    # Create visualization script
    cat > "$INSTALL_DIR/visualize_schedule.sh" << EOF
#!/bin/bash
source "$INSTALL_DIR/$VENV_NAME/bin/activate"
cd "$INSTALL_DIR/schedule_management"
python reminder_macos.py --visualize
EOF
    
    # Create CLI tool wrapper script
    cat > "$INSTALL_DIR/reminder" << EOF
#!/bin/bash
# CLI tool wrapper for the reminder system
source "$INSTALL_DIR/$VENV_NAME/bin/activate"
reminder "\$@"
EOF
    
    # Make scripts executable
    chmod +x "$INSTALL_DIR"/*.sh
    chmod +x "$INSTALL_DIR/reminder"
    
    log_success "Convenience scripts created"
}

# Create desktop shortcuts (optional)
create_shortcuts() {
    log_info "Creating desktop shortcuts..."
    
    # Create AppleScript app for easy access
    mkdir -p "$HOME/Desktop/Healthy Habits.app/Contents/MacOS"
    
    cat > "$HOME/Desktop/Healthy Habits.app/Contents/MacOS/Healthy Habits" << 'EOF'
#!/bin/bash
open -a Terminal "$HOME/healthy_habits/start_reminders.sh"
EOF
    
    chmod +x "$HOME/Desktop/Healthy Habits.app/Contents/MacOS/Healthy Habits"
    
    # Create Info.plist for the app
    cat > "$HOME/Desktop/Healthy Habits.app/Contents/Info.plist" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleExecutable</key>
    <string>Healthy Habits</string>
    <key>CFBundleIdentifier</key>
    <string>com.health.habits.app</string>
    <key>CFBundleName</key>
    <string>Healthy Habits</string>
    <key>CFBundleVersion</key>
    <string>1.0</string>
</dict>
</plist>
EOF
    
    log_success "Desktop shortcut created"
}

# Test installation
test_installation() {
    log_info "Testing installation..."
    
    # Test Python import
    if [[ -f "$INSTALL_DIR/$VENV_NAME/bin/activate" ]]; then
        source "$INSTALL_DIR/$VENV_NAME/bin/activate"
        if python -c "import matplotlib; print('matplotlib imported successfully')"; then
            log_success "Python dependencies test passed"
        else
            log_error "Python dependencies test failed"
            exit 1
        fi
        
        # Test that the schedule-management package is installed
        if python -c "import schedule_management; print('schedule_management package imported successfully')"; then
            log_success "Schedule-management package test passed"
        else
            log_error "Schedule-management package test failed"
            exit 1
        fi
        
        # Test that the reminder CLI command is available
        if command -v reminder &> /dev/null; then
            log_success "CLI tool 'reminder' is available"
            # Test the reminder command help
            if reminder --help &> /dev/null; then
                log_success "CLI tool 'reminder' is working correctly"
            else
                log_warning "CLI tool 'reminder' is available but may have issues"
            fi
        else
            log_error "CLI tool 'reminder' is not available"
            exit 1
        fi
    else
        log_warning "Virtual environment activation script not found, skipping Python test"
    fi
    
    # Test configuration files
    if [[ -f "$INSTALL_DIR/config/settings.toml" ]]; then
        log_success "Configuration files test passed"
    else
        log_warning "Configuration files not found - will use defaults"
    fi
    
    log_success "Installation test completed"
}

# Display usage information
display_usage() {
    log_info "Installation completed successfully!"
    echo
    echo "=== CLI Tool Usage ==="
    echo "Add $INSTALL_DIR to your PATH or use full path:"
    echo "  $INSTALL_DIR/reminder update    # Update configuration and restart service"
    echo "  $INSTALL_DIR/reminder view      # Generate schedule visualizations"
    echo "  $INSTALL_DIR/reminder status    # Show current status and next events"
    echo "  $INSTALL_DIR/reminder status -v # Show detailed status with full schedule"
    echo
    echo "=== Manual Scripts ==="
    echo "1. Manual start: $INSTALL_DIR/start_reminders.sh"
    echo "2. Manual stop: $INSTALL_DIR/stop_reminders.sh"
    echo "3. Restart service: $INSTALL_DIR/restart_reminders.sh"
    echo "4. Generate visualizations: $INSTALL_DIR/visualize_schedule.sh"
    echo
    echo "=== LaunchAgent Management ==="
    echo "Load service: launchctl load $LAUNCH_AGENT_PLIST"
    echo "Unload service: launchctl unload $LAUNCH_AGENT_PLIST"
    echo
    echo "=== Configuration ==="
    echo "Settings: $INSTALL_DIR/config/settings.toml"
    echo "Odd week schedule: $INSTALL_DIR/config/odd_weeks.toml"
    echo "Even week schedule: $INSTALL_DIR/config/even_weeks.toml"
    echo
    echo "=== Logs ==="
    echo "Output logs: $INSTALL_DIR/logs/healthy_habits.out"
    echo "Error logs: $INSTALL_DIR/logs/healthy_habits.err"
    echo
    echo "=== Setup CLI Tool ==="
    echo "To use 'reminder' command globally, add to your PATH:"
    echo "  export PATH=\"$INSTALL_DIR:\$PATH\""
    echo "Add this line to your ~/.zshrc or ~/.bash_profile"
    echo
    log_warning "You may need to grant accessibility permissions when the app first runs."
    log_info "The reminder system will start automatically on next login if LaunchAgent is loaded."
}

# Cleanup function
cleanup() {
    if [[ -n "${VIRTUAL_ENV:-}" ]]; then
        deactivate 2>/dev/null || true
    fi
}

# Main installation function
main() {
    echo "=== $SCRIPT_NAME ==="
    echo "Setting up Awesome Healthy Habits reminder system for macOS"
    echo
    
    # Set trap for cleanup
    trap cleanup EXIT
    
    # Run installation steps
    check_macos
    check_homebrew
    check_uv
    install_python
    setup_project
    create_venv
    install_dependencies
    create_launch_agent
    request_permissions
    create_scripts
    create_shortcuts
    test_installation
    display_usage
    
    log_success "Installation completed! 🎉"
    log_info "Your healthy habits reminder system is ready to use."
}

# Handle command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            echo "Usage: $0 [OPTIONS]"
            echo
            echo "Options:"
            echo "  -h, --help     Show this help message"
            echo "  -v, --verbose  Enable verbose output"
            echo "  --no-launch    Skip LaunchAgent creation"
            echo "  --no-desktop   Skip desktop shortcut creation"
            echo
            echo "This script installs the Awesome Healthy Habits reminder system on macOS."
            exit 0
            ;;
        -v|--verbose)
            set -x
            shift
            ;;
        --no-launch)
            SKIP_LAUNCH=true
            shift
            ;;
        --no-desktop)
            SKIP_DESKTOP=true
            shift
            ;;
        *)
            log_error "Unknown option: $1"
            echo "Use -h or --help for usage information"
            exit 1
            ;;
    esac
done

# Run main function
main