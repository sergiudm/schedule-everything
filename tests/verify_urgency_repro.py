import json
import os
import sys
from unittest.mock import MagicMock

# Add src to path
sys.path.append(os.path.join(os.getcwd(), "src"))

# Create dummy files
os.makedirs("tests/temp_config/tasks", exist_ok=True)

# 1. Create settings.toml with daily_urgency
with open("tests/temp_config/settings.toml", "w") as f:
    f.write("""
[tasks]
daily_urgent = ["10:00", "20:00"]
""")

# 2. Create tasks.json with urgent and non-urgent tasks
tasks_data = [
    {"description": "Low Priority", "priority": 1},
    {"description": "Medium Priority", "priority": 5},
    {"description": "High Priority", "priority": 8},
    {"description": "Critical Priority", "priority": 10},
]
with open("tests/temp_config/tasks/tasks.json", "w") as f:
    json.dump(tasks_data, f)

# Import the module
from schedule_management import reminder_macos

# Patch the file paths directly on the module
reminder_macos.SETTINGS_PATH = "tests/temp_config/settings.toml"
reminder_macos.TASKS_PATH = "tests/temp_config/tasks/tasks.json"

# Test ScheduleConfig
print("--- Testing ScheduleConfig ---")
config = reminder_macos.ScheduleConfig("tests/temp_config/settings.toml")
print(f"Config loaded tasks keys: {config.tasks.keys()}")
print(f"daily_urgent_times property: {config.daily_urgent_times}")

if not config.daily_urgent_times:
    print("FAILURE: daily_urgent_times is empty. 'daily_urgency' key was ignored.")
else:
    print(f"SUCCESS: daily_urgent_times found: {config.daily_urgent_times}")

# Test urgency logic
print("\n--- Testing Urgency Logic ---")
# We need a dummy weekly schedule to init runner
mock_weekly = MagicMock()
runner = reminder_macos.ScheduleRunner(config, mock_weekly)

urgent_tasks = runner._get_unfinished_urgent_tasks()
print(f"Found {len(urgent_tasks)} urgent tasks:")
for t in urgent_tasks:
    print(f"- {t['description']} (Priority: {t['priority']})")

expected_count = 2 # 8 and 10
if len(urgent_tasks) == expected_count:
    print(f"SUCCESS: Correctly identified {expected_count} urgent tasks (priority > 7).")
else:
    print(f"FAILURE: Expected {expected_count} urgent tasks, found {len(urgent_tasks)}.")