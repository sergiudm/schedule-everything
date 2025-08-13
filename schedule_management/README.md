# Schedule Management

This script provides a simple way to manage your daily schedule and receive reminders on macOS. It uses a Python script to trigger notifications based on a predefined schedule.

> [!NOTE]
> This script is designed for macOS. Support for other operating systems may be added in the future.

## Features

- **Customizable Schedule**: Easily define your own schedule and reminder messages in the `reminder_macos.py` script.
- **Audible and Visual Alerts**: Get both a sound notification and a dialog box for each reminder.
- **Persistent Reminders**: The alarm will repeat until you dismiss the dialog.
- **Automatic Execution**: Can be configured to run automatically on system startup using `launchd`.

## How It Works

The `reminder_macos.py` script contains a dictionary called `schedule` where you can define your daily tasks and their corresponding times. The script runs in a loop, checking the current time and triggering an alarm when it matches a scheduled time.

### Configuration

1.  **Edit the schedule**: Open [`schedule_management/reminder_macos.py`](schedule_management/reminder_macos.py) and modify the `schedule` dictionary to fit your needs. The key is the time in "HH:MM" format, and the value is the message you want to see.
2.  **Change the sound (optional)**: You can change the notification sound by modifying the `SOUND_FILE` variable.

### Manual Execution

You can run the script manually from your terminal:

```bash
python3 schedule_management/reminder_macos.py
```

### Automatic Execution with `launchd`

To run the script automatically in the background, you can use `launchd`, the standard way to manage daemons and agents on macOS. A sample `.plist` file is provided.

1.  **Edit the `.plist` file**: You will need to create a file like `com.user.schedule_notify.plist` in `~/Library/LaunchAgents/`. Make sure the `ProgramArguments` key points to the correct path of your python interpreter and the `reminder_macos.py` script.
2.  **Load the agent**:
    ```bash
    launchctl load ~/Library/LaunchAgents/com.user.schedule_notify.plist
    ```
3.  **Start the agent**:
    ```bash
    launchctl start com.user.schedule_notify
    ```

To stop the agent:

```bash
launchctl unload ~/Library/LaunchAgents/com.user.schedule_notify.plist
