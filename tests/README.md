# Water Python API - Unit Tests

This directory contains comprehensive unit tests for the water-python-api project.

## Overview

The test suite uses **pytest** with extensive mocking to test all components without requiring actual database or API infrastructure. This allows the tests to run in CI/CD environments like GitHub Actions.

## Test Files

- **test_water_meter_daemon.py**: 25 tests for `water-python-api.py`
  - Daemon initialization
  - Database connection and schema setup
  - API meter reading
  - Data storage
  - Health checks
  - Main daemon loop

- **test_maintenance_logger.py**: 27 tests for `maintenance-logger.py`
  - Logger initialization
  - Database connection
  - Maintenance logging
  - Recent maintenance listing
  - Last salt replacement tracking
  - Last change tracking (new feature)
  - CLI command execution

## Running Tests

### Local Testing

1. **Install test dependencies**:
   ```bash
   pip install -r requirements-test.txt
   ```

2. **Run all tests**:
   ```bash
   pytest tests/
   ```

3. **Run with verbose output**:
   ```bash
   pytest tests/ -v
   ```

4. **Run specific test file**:
   ```bash
   pytest tests/test_water_meter_daemon.py -v
   ```

5. **Run with coverage report**:
   ```bash
   pytest tests/ --cov=. --cov-report=term-missing
   ```

6. **Run only unit tests** (fast tests with no external dependencies):
   ```bash
   pytest tests/ -m unit
   ```

### GitHub Actions

Tests run automatically on:
- Push to `main` or `feature/*` branches
- Pull requests to `main`

The workflow tests against Python versions 3.9, 3.10, 3.11, and 3.12.

## Test Strategy

### Mocking Approach

All tests use mocking to avoid external dependencies:

1. **Database Mocking**:
   - `psycopg2.connect()` is mocked to return fake connections
   - Cursors and query results are mocked
   - No actual PostgreSQL/TimescaleDB required

2. **API Mocking**:
   - `requests.get()` is mocked for meter API calls
   - Responses are simulated with test data
   - No actual water meter API required

3. **Environment Variables**:
   - `pytest.monkeypatch` sets test environment variables
   - Each test runs in isolation with clean environment

### Test Coverage

Current coverage: **52 tests, 100% pass rate**

**water-python-api.py** coverage:
- ✅ Initialization with env vars and defaults
- ✅ Signal handling for graceful shutdown
- ✅ Database connection (success, failure, auto-create)
- ✅ Schema setup with TimescaleDB
- ✅ Meter reading (success, errors, invalid data)
- ✅ Safe float conversion
- ✅ Data storage
- ✅ Health checks with reconnection
- ✅ Main loop with failure handling

**maintenance-logger.py** coverage:
- ✅ Initialization and configuration
- ✅ Database connectivity
- ✅ Maintenance logging (all fields)
- ✅ Listing recent maintenance
- ✅ Last salt replacement query
- ✅ Last change query (any type)
- ✅ All CLI commands (salt, log, list, last-salt, last-change)
- ✅ Connection cleanup in finally block

## Test Markers

Tests are categorized with markers:

- `@pytest.mark.unit`: Fast unit tests (no external dependencies)
- `@pytest.mark.integration`: Integration tests (may require services)
- `@pytest.mark.slow`: Slow-running tests

## Continuous Integration

### Test Workflow

The `.github/workflows/tests.yml` workflow includes:

1. **Test Job**:
   - Runs on Ubuntu with Python 3.9-3.12
   - Installs dependencies from requirements-test.txt
   - Executes full test suite with coverage
   - Uploads coverage to Codecov

2. **Lint Job**:
   - Runs flake8 for syntax errors
   - Checks code quality

3. **Security Job**:
   - Runs Bandit security scanner
   - Checks for known vulnerabilities with Safety

## Writing New Tests

### Test Template

```python
import pytest
from unittest.mock import Mock, MagicMock, patch

@pytest.mark.unit
class TestMyFeature:
    """Test my new feature"""

    def test_feature_success(self, daemon):
        """Test successful feature execution"""
        # Arrange
        mock_obj = MagicMock()

        # Act
        result = daemon.my_method()

        # Assert
        assert result is True
```

### Best Practices

1. **Use descriptive test names**: `test_<method>_<scenario>`
2. **Follow AAA pattern**: Arrange, Act, Assert
3. **Mock external dependencies**: Database, API calls, file I/O
4. **Test both success and failure paths**
5. **Use fixtures for common setup**
6. **Add docstrings to explain what's being tested**

## Dependencies

- **pytest**: Testing framework
- **pytest-cov**: Coverage reporting
- **pytest-mock**: Enhanced mocking utilities
- **psycopg2-binary**: PostgreSQL adapter (for imports)
- **requests**: HTTP library (for imports)
- **coverage**: Code coverage measurement

## Troubleshooting

### Import Errors

If you see module import errors, ensure you're running pytest from the project root:
```bash
cd /path/to/water-python-api
pytest tests/
```

### Environment Variable Errors

Tests should handle missing environment variables gracefully. If you see errors, check that:
- Fixtures properly set up `monkeypatch.setenv()`
- Module loading occurs after env vars are set

### Mock Not Working

Ensure you're patching at the right location:
```python
# Patch where it's used, not where it's defined
@patch('psycopg2.connect')  # ✅ Correct
@patch('psycopg2.extensions.connect')  # ❌ Wrong
```

## Future Improvements

- [ ] Add integration tests with actual test database
- [ ] Add performance/benchmark tests
- [ ] Add property-based testing with Hypothesis
- [ ] Increase coverage to 100%
- [ ] Add mutation testing

## References

- [pytest documentation](https://docs.pytest.org/)
- [unittest.mock guide](https://docs.python.org/3/library/unittest.mock.html)
- [pytest-cov documentation](https://pytest-cov.readthedocs.io/)
