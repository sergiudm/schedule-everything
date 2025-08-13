#!/usr/bin/env python3
"""
Test runner script for the schedule management project.
Run this script to execute all tests with coverage reporting.
"""

import subprocess
import sys
from pathlib import Path

def run_tests(pytest_args=None):
    """
    Run pytest with coverage and generate reports.
    
    :param pytest_args: A list of additional arguments to pass to pytest.
    """
    if pytest_args is None:
        pytest_args = []
        
    # Ensure we're in the right directory
    project_root = Path(__file__).parent.parent
    
    # Base pytest command
    command = [
        sys.executable, "-m", "pytest",
        "--verbose",
        "--cov=.",
        "--cov-report=term-missing",
        "--cov-report=html:htmlcov",
        "--tb=short"
    ]
    
    # Add any extra arguments
    command.extend(pytest_args)

    # If no specific files are provided, default to running all tests
    if not any(arg for arg in pytest_args if not arg.startswith('-')):
        command.append(str(project_root / "tests"))

    # Run tests
    print(f"\nRunning tests with command: {' '.join(command)}")
    result = subprocess.run(command, cwd=project_root)
    
    if result.returncode == 0:
        print("\n✅ All tests passed!")
        print("📊 Coverage report generated in htmlcov/index.html")
    else:
        print("\n❌ Some tests failed!")
        sys.exit(1)

if __name__ == "__main__":
    # Pass command-line arguments (excluding the script name) to pytest
    run_tests(sys.argv[1:])