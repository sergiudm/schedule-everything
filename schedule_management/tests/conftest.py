import pytest
import sys
from pathlib import Path

# Add the parent directory to sys.path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

@pytest.fixture(autouse=True)
def setup_test_environment():
    """Setup test environment before each test"""
    # Reset any global state if needed
    yield
    # Cleanup after test if needed
    pass

@pytest.fixture
def mock_subprocess_success():
    """Mock successful subprocess calls"""
    from unittest.mock import MagicMock
    mock = MagicMock()
    mock.return_value.stdout = "success"
    mock.return_value.returncode = 0
    return mock