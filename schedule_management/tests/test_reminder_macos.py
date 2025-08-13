import pytest
import subprocess
import tempfile
import tomllib
from pathlib import Path
from unittest.mock import patch, mock_open, MagicMock
import sys
import os

# Add the parent directory to sys.path to import the module
sys.path.insert(0, str(Path(__file__).parent.parent))

import reminder_macos


class TestLoadConfig:
    """Test configuration loading functionality"""
    
    def test_load_config_success(self, tmp_path):
        """Test successful configuration loading"""
        config_content = """
[settings]
sound_file = "/System/Library/Sounds/Ping.aiff"
alarm_interval = 30
max_alarm_duration = 300

[schedule]
"08:00" = "Wake up!"
"12:00" = "Lunch time"
"""
        config_file = tmp_path / "schedule.toml"
        config_file.write_text(config_content)
        
        with patch('reminder_macos.Path') as mock_path:
            mock_path.return_value.parent = tmp_path
            mock_path.__file__ = str(tmp_path / "reminder_macos.py")
            
            # Mock the path resolution
            with patch('pathlib.Path') as mock_pathlib:
                mock_pathlib.return_value.parent = tmp_path
                mock_pathlib.return_value.__truediv__ = lambda self, other: tmp_path / other
                
                # Create a mock path object that behaves correctly
                mock_config_path = MagicMock()
                mock_config_path.exists.return_value = True
                
                with patch('builtins.open', mock_open(read_data=config_content.encode())):
                    with patch('tomllib.load') as mock_load:
                        expected_config = {
                            'settings': {
                                'sound_file': '/System/Library/Sounds/Ping.aiff',
                                'alarm_interval': 30,
                                'max_alarm_duration': 300
                            },
                            'schedule': {
                                '08:00': 'Wake up!',
                                '12:00': 'Lunch time'
                            }
                        }
                        mock_load.return_value = expected_config
                        
                        with patch.object(Path, 'exists', return_value=True):
                            result = reminder_macos.load_config()
                            assert result == expected_config

    def test_load_config_file_not_found(self):
        """Test configuration loading when file doesn't exist"""
        with patch('pathlib.Path') as mock_path:
            mock_config_path = MagicMock()
            mock_config_path.exists.return_value = False
            mock_path.return_value.parent.__truediv__.return_value = mock_config_path
            
            with pytest.raises(FileNotFoundError):
                reminder_macos.load_config()


class TestPlaySound:
    """Test sound playing functionality"""
    
    @patch('subprocess.Popen')
    def test_play_sound(self, mock_popen):
        """Test that play_sound calls afplay with correct sound file"""
        reminder_macos.play_sound()
        mock_popen.assert_called_once_with(["afplay", reminder_macos.SOUND_FILE])


class TestShowDialog:
    """Test dialog display functionality"""
    
    @patch('subprocess.run')
    def test_show_dialog_success(self, mock_run):
        """Test successful dialog display"""
        mock_run.return_value.stdout = 'button returned:停止闹铃\n'
        
        result = reminder_macos.show_dialog("Test message")
        
        expected_command = [
            "osascript",
            "-e",
            'display dialog "Test message" buttons {"停止闹铃"} default button "停止闹铃"'
        ]
        mock_run.assert_called_once_with(
            expected_command,
            capture_output=True,
            text=True
        )
        assert result == 'button returned:停止闹铃'

    @patch('subprocess.run')
    def test_show_dialog_with_special_characters(self, mock_run):
        """Test dialog with special characters in message"""
        mock_run.return_value.stdout = 'button returned:停止闹铃\n'
        
        message = "Test with \"quotes\" and 'apostrophes'"
        reminder_macos.show_dialog(message)
        
        expected_command = [
            "osascript",
            "-e",
            f'display dialog "{message}" buttons {{"停止闹铃"}} default button "停止闹铃"'
        ]
        mock_run.assert_called_once_with(
            expected_command,
            capture_output=True,
            text=True
        )


class TestAlarm:
    """Test alarm functionality"""
    
    @patch('reminder_macos.show_dialog')
    @patch('reminder_macos.play_sound')
    @patch('time.sleep')
    def test_alarm_stops_on_button_click(self, mock_sleep, mock_play_sound, mock_show_dialog):
        """Test that alarm stops when user clicks stop button"""
        mock_show_dialog.return_value = "停止闹铃"
        
        reminder_macos.alarm("Test Title", "Test Message")
        
        mock_play_sound.assert_called_once()
        mock_show_dialog.assert_called_once_with("Test Message")
        mock_sleep.assert_not_called()

    @patch('reminder_macos.show_dialog')
    @patch('reminder_macos.play_sound')
    @patch('time.sleep')
    @patch('time.time')
    def test_alarm_stops_on_max_duration(self, mock_time, mock_sleep, mock_play_sound, mock_show_dialog):
        """Test that alarm stops after maximum duration"""
        # Mock time to simulate timeout
        mock_time.side_effect = [0, 0, 350]  # Start, first check, timeout check
        mock_show_dialog.return_value = "other"
        
        reminder_macos.alarm("Test Title", "Test Message")
        
        assert mock_play_sound.call_count >= 1
        assert mock_show_dialog.call_count >= 1

    @patch('reminder_macos.show_dialog')
    @patch('reminder_macos.play_sound')
    @patch('time.sleep')
    @patch('time.time')
    def test_alarm_repeats_until_stopped(self, mock_time, mock_sleep, mock_play_sound, mock_show_dialog):
        """Test that alarm repeats until user stops it"""
        # First two calls return "other", third returns stop
        mock_show_dialog.side_effect = ["other", "other", "停止闹铃"]
        mock_time.side_effect = [0, 0, 0, 0]  # Always return 0 to avoid timeout
        
        reminder_macos.alarm("Test Title", "Test Message")
        
        assert mock_play_sound.call_count == 3
        assert mock_show_dialog.call_count == 3
        assert mock_sleep.call_count == 2


class TestConfigurationValues:
    """Test configuration value handling"""
    
    def test_default_sound_file(self):
        """Test default sound file path"""
        assert reminder_macos.SOUND_FILE == "/System/Library/Sounds/Ping.aiff"
    
    def test_default_alarm_interval(self):
        """Test default alarm interval"""
        assert reminder_macos.ALARM_INTERVAL == 5  # From the loaded config
    
    def test_default_max_alarm_duration(self):
        """Test default max alarm duration"""
        assert reminder_macos.MAX_ALARM_DURATION == 300


class TestIntegration:
    """Integration tests for the reminder system"""
    
    @patch('reminder_macos.show_dialog')
    @patch('reminder_macos.play_sound')
    @patch('time.sleep')
    def test_full_alarm_cycle(self, mock_sleep, mock_play_sound, mock_show_dialog):
        """Test a complete alarm cycle"""
        mock_show_dialog.return_value = "停止闹铃"
        
        # Test the alarm function with realistic parameters
        reminder_macos.alarm("作息提醒", "起床啦！")
        
        # Verify the alarm played sound and showed dialog
        mock_play_sound.assert_called_once()
        mock_show_dialog.assert_called_once_with("起床啦！")


# Fixtures for testing
@pytest.fixture
def sample_config():
    """Provide a sample configuration for testing"""
    return {
        'settings': {
            'sound_file': '/System/Library/Sounds/Ping.aiff',
            'alarm_interval': 30,
            'max_alarm_duration': 300
        },
        'schedule': {
            '08:00': 'Wake up!',
            '12:00': 'Lunch time',
            '18:00': 'Dinner time'
        }
    }


@pytest.fixture
def temp_config_file(tmp_path, sample_config):
    """Create a temporary config file for testing"""
    config_content = """
[settings]
sound_file = "/System/Library/Sounds/Ping.aiff"
alarm_interval = 30
max_alarm_duration = 300

[schedule]
"08:00" = "Wake up!"
"12:00" = "Lunch time"
"18:00" = "Dinner time"
"""
    config_file = tmp_path / "schedule.toml"
    config_file.write_text(config_content)
    return config_file