# Testing Guide

## Overview

This document provides comprehensive testing instructions for the VLAN Cleanup Automation solution. The testing framework includes unit tests, integration tests, and performance tests to ensure reliable operation in production environments.

## Test Structure

```
tests/
├── conftest.py              # Shared fixtures and utilities
├── unit/                    # Unit tests for individual modules
│   ├── test_models.py       # Data model tests
│   ├── test_config.py       # Configuration management tests
│   ├── test_device_handler.py # Device communication tests
│   ├── test_processor.py    # Core processing logic tests
│   └── test_reporting.py    # Report generation tests
└── integration/             # Integration and end-to-end tests
    └── test_integration.py  # Component interaction tests
```

## Test Categories

### 🧪 Unit Tests
- **Purpose**: Test individual functions and classes in isolation
- **Coverage**: Each module in `src/` directory
- **Execution Time**: Fast (< 1 minute)
- **Dependencies**: Mocked external dependencies

### 🔗 Integration Tests
- **Purpose**: Test component interactions and workflows
- **Coverage**: Multi-component scenarios and end-to-end workflows
- **Execution Time**: Moderate (1-5 minutes)
- **Dependencies**: Real component integration with mocked network calls

### 🚀 Performance Tests
- **Purpose**: Test scalability and performance characteristics
- **Coverage**: Large-scale device processing scenarios
- **Execution Time**: Slow (5+ minutes)
- **Dependencies**: Simulated large-scale environments

## Quick Start

### 1. Install Test Dependencies

```bash
# Install main dependencies
pip install -r requirements.txt

# Install test dependencies
pip install -r requirements-test.txt
```

### 2. Run All Tests

```bash
# Using the test runner script (recommended)
python run_tests.py --all --verbose --coverage

# Using pytest directly
pytest tests/ --cov=src --cov-report=html --cov-report=term-missing -v
```

### 3. View Coverage Report

```bash
# Open HTML coverage report
open htmlcov/index.html  # macOS
xdg-open htmlcov/index.html  # Linux
start htmlcov/index.html  # Windows
```

## Test Execution Options

### Using the Test Runner Script

The `run_tests.py` script provides convenient commands for different testing scenarios:

```bash
# Run unit tests only
python run_tests.py --unit --verbose

# Run integration tests only
python run_tests.py --integration --verbose

# Run all tests with coverage
python run_tests.py --all --coverage --verbose

# Run specific test file
python run_tests.py --test tests/unit/test_models.py --verbose

# Run specific test method
python run_tests.py --test tests/unit/test_models.py::TestVLANInfo::test_vlan_info_creation

# Generate comprehensive test report
python run_tests.py --report

# Check test dependencies
python run_tests.py --check-deps

# Run code linting
python run_tests.py --lint

# Run performance tests
python run_tests.py --performance
```

### Using pytest Directly

```bash
# Run all tests
pytest tests/

# Run unit tests only
pytest tests/unit/ -m unit

# Run integration tests only
pytest tests/integration/ -m integration

# Run tests with coverage
pytest tests/ --cov=src --cov-report=html

# Run specific test file
pytest tests/unit/test_models.py -v

# Run tests matching pattern
pytest tests/ -k "test_vlan" -v

# Run tests and stop on first failure
pytest tests/ -x

# Run tests in parallel (if pytest-xdist installed)
pytest tests/ -n auto
```

## Test Configuration

### pytest.ini Settings

The `pytest.ini` file configures test execution:

```ini
[tool:pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts = 
    --verbose
    --tb=short
    --cov=src
    --cov-report=html
    --cov-report=term-missing
    --cov-fail-under=80
markers =
    unit: Unit tests
    integration: Integration tests
    slow: Slow tests (require network access)
    mock: Tests using mocks
```

### Test Markers

Tests are categorized using pytest markers:

- `@pytest.mark.unit`: Unit tests
- `@pytest.mark.integration`: Integration tests
- `@pytest.mark.slow`: Performance/slow tests
- `@pytest.mark.mock`: Tests using mocks

## Test Data and Fixtures

### Common Fixtures

The `conftest.py` file provides shared fixtures:

```python
# Configuration fixtures
temp_config_file()          # Temporary test configuration
config_manager()            # ConfigManager instance

# Data model fixtures
sample_device_info()        # Sample device information
sample_vlan_info()          # Sample VLAN data
sample_processing_result()  # Sample processing result

# Mock fixtures
mock_netmiko_connection()   # Mocked network connection
cisco_vlan_output()         # Sample Cisco VLAN output
arista_vlan_output()        # Sample Arista VLAN output
juniper_vlan_output()       # Sample Juniper VLAN output
```

### Test Data Guidelines

1. **Use Fixtures**: Leverage shared fixtures for consistent test data
2. **Mock External Dependencies**: Mock network connections and external services
3. **Realistic Data**: Use realistic device configurations and VLAN data
4. **Edge Cases**: Include edge cases and error conditions

## Writing New Tests

### Unit Test Example

```python
import pytest
from src.models import VLANInfo

class TestVLANInfo:
    """Test cases for VLANInfo model."""
    
    def test_vlan_creation(self):
        """Test VLAN object creation."""
        vlan = VLANInfo(
            vlan_id=100,
            name='test-vlan',
            status='active',
            ports=['Gi1/0/1']
        )
        
        assert vlan.vlan_id == 100
        assert vlan.name == 'test-vlan'
        assert vlan.is_unused is False  # default
    
    @pytest.mark.parametrize("vlan_id,expected_risk", [
        (1, "high"),      # Management range
        (100, "medium"),  # Voice range
        (500, "low")      # Normal range
    ])
    def test_risk_assessment(self, vlan_id, expected_risk):
        """Test risk level assessment."""
        # Test implementation here
        pass
```

### Integration Test Example

```python
@pytest.mark.integration
class TestEndToEndWorkflow:
    """Integration tests for complete workflows."""
    
    def test_complete_dry_run_workflow(self, temp_config_file):
        """Test complete dry-run workflow."""
        processor = VLANCleanupProcessor(temp_config_file, dry_run=True)
        
        # Mock external dependencies
        with patch.object(processor.device_handler, 'connect_to_device') as mock_connect:
            mock_connect.return_value = mock_connection
            
            # Execute workflow
            results = processor.process_devices()
            
            # Verify results
            assert len(results) > 0
            assert all(r.status == 'success' for r in results)
```

### Mock Guidelines

1. **Mock External Services**: Always mock network connections and external APIs
2. **Realistic Responses**: Provide realistic mock responses
3. **Error Scenarios**: Test error conditions with appropriate mocks
4. **Side Effects**: Use side_effect for dynamic mock behavior

```python
# Mock connection with side effects
def mock_send_command(command):
    if command == "show vlan brief":
        return cisco_vlan_output
    elif command.startswith("show interface vlan"):
        return "Interface not found"
    return ""

mock_connection.send_command.side_effect = mock_send_command
```

## Coverage Requirements

### Minimum Coverage Targets

- **Overall Coverage**: 80% minimum
- **Unit Tests**: 90% minimum per module
- **Integration Tests**: 70% minimum
- **Critical Paths**: 95% minimum (device connection, VLAN processing)

### Coverage Exclusions

Certain code is excluded from coverage requirements:

```python
# In source code, use pragma to exclude lines
def debug_function():  # pragma: no cover
    pass

# Exclude from coverage.ini
[coverage:report]
exclude_lines =
    pragma: no cover
    def __repr__
    raise AssertionError
    raise NotImplementedError
```

## Continuous Integration

### GitHub Actions Setup

```yaml
# .github/workflows/tests.yml
name: Tests
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: [3.8, 3.9, "3.10", "3.11"]
    
    steps:
    - uses: actions/checkout@v3
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: ${{ matrix.python-version }}
    
    - name: Install dependencies
      run: |
        pip install -r requirements.txt
        pip install -r requirements-test.txt
    
    - name: Run tests
      run: python run_tests.py --all --coverage --lint
    
    - name: Upload coverage
      uses: codecov/codecov-action@v3
      with:
        file: ./coverage.xml
```

## Performance Testing

### Large Scale Testing

```python
@pytest.mark.slow
def test_large_scale_processing():
    """Test processing of many devices."""
    # Create config with 100+ devices
    devices = [create_test_device(i) for i in range(100)]
    
    # Mock fast responses
    with patch_device_connections():
        processor = VLANCleanupProcessor(config, dry_run=True)
        results = processor.process_devices()
    
    # Verify performance characteristics
    assert len(results) == 100
    assert processing_time < 60  # seconds
```

### Memory Testing

```python
def test_memory_usage():
    """Test memory usage with large datasets."""
    import psutil
    import os
    
    process = psutil.Process(os.getpid())
    initial_memory = process.memory_info().rss
    
    # Process large dataset
    processor = VLANCleanupProcessor(large_config)
    results = processor.process_devices()
    
    final_memory = process.memory_info().rss
    memory_increase = final_memory - initial_memory
    
    # Memory increase should be reasonable
    assert memory_increase < 100 * 1024 * 1024  # 100MB max
```

## Debugging Tests

### Running Tests in Debug Mode

```bash
# Run with Python debugger
python -m pytest tests/unit/test_models.py::TestVLANInfo::test_creation --pdb

# Run with verbose output and no capture
python -m pytest tests/unit/test_models.py -v -s

# Run and stop on first failure
python -m pytest tests/ -x --tb=long
```

### VS Code Integration

```json
// .vscode/settings.json
{
    "python.testing.pytestEnabled": true,
    "python.testing.pytestArgs": [
        "tests"
    ],
    "python.testing.unittestEnabled": false
}
```

## Troubleshooting

### Common Issues

1. **Import Errors**
   ```bash
   # Solution: Add project root to PYTHONPATH
   export PYTHONPATH="${PYTHONPATH}:$(pwd)"
   ```

2. **Missing Dependencies**
   ```bash
   # Solution: Install test dependencies
   pip install -r requirements-test.txt
   ```

3. **Coverage Too Low**
   ```bash
   # Solution: Check uncovered lines
   pytest tests/ --cov=src --cov-report=html
   open htmlcov/index.html
   ```

4. **Slow Tests**
   ```bash
   # Solution: Run fast tests only
   pytest tests/ -m "not slow"
   ```

### Getting Help

- **GitHub Issues**: Report test failures and bugs
- **Documentation**: Check module docstrings and comments
- **Test Output**: Review detailed test output and logs

## Best Practices

### Test Organization

1. **One Test Class per Module**: Mirror source code structure
2. **Descriptive Names**: Use clear, descriptive test method names
3. **Arrange-Act-Assert**: Follow AAA pattern in test methods
4. **Test Independence**: Each test should be independent

### Test Data Management

1. **Use Fixtures**: Leverage pytest fixtures for shared data
2. **Parameterized Tests**: Use parametrize for multiple test cases
3. **Realistic Data**: Use realistic test data that matches production
4. **Clean Setup/Teardown**: Ensure proper test cleanup

### Mocking Strategy

1. **Mock External Dependencies**: Always mock network and file operations
2. **Patch at Usage Point**: Patch where the function is used, not defined
3. **Verify Mock Calls**: Assert that mocks were called correctly
4. **Reset Mocks**: Ensure mocks are reset between tests

### Performance Considerations

1. **Fast Unit Tests**: Keep unit tests fast (< 1 second each)
2. **Mark Slow Tests**: Use @pytest.mark.slow for long-running tests
3. **Parallel Execution**: Consider pytest-xdist for parallel test execution
4. **Resource Cleanup**: Properly clean up resources in tests

---

**Happy Testing! 🧪** 

Comprehensive testing ensures reliable automation and builds confidence in production deployments.
