# Testing

To ensure the script is working as expected, you can run the provided tests. The test runner has been designed to be flexible, allowing you to run all tests or specific ones.

## Running All Tests

To run the complete test suite, use the following command:

```bash
uv run python tests/run_tests.py
```

This will execute all tests and provide a coverage report.

## Running Specific Tests

You can also pass arguments to `pytest` through the `run_tests.py` script. For example, to run a specific test file:

```bash
uv run python tests/run_tests.py tests/test_reminder_macos.py
```

To run a specific test case by name:

```bash
uv run python tests/run_tests.py -k "TestAlarm"
```

This flexibility allows for faster, more targeted testing during development.