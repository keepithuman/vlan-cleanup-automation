#!/usr/bin/env python3
"""
Test runner script for VLAN cleanup automation.
Provides convenient commands for running different types of tests.
"""
import sys
import subprocess
import argparse
from pathlib import Path


def run_command(cmd, description):
    """Run a command and handle errors."""
    print(f"\n{'='*60}")
    print(f"Running: {description}")
    print(f"Command: {' '.join(cmd)}")
    print('='*60)
    
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        print(result.stdout)
        if result.stderr:
            print("STDERR:", result.stderr)
        return True
    except subprocess.CalledProcessError as e:
        print(f"ERROR: Command failed with return code {e.returncode}")
        print("STDOUT:", e.stdout)
        print("STDERR:", e.stderr)
        return False


def run_unit_tests(verbose=False, coverage=False):
    """Run unit tests."""
    cmd = ['python', '-m', 'pytest', 'tests/unit/']
    
    if verbose:
        cmd.append('-v')
    
    if coverage:
        cmd.extend(['--cov=src', '--cov-report=html', '--cov-report=term-missing'])
    
    cmd.append('-m')
    cmd.append('unit')
    
    return run_command(cmd, "Unit Tests")


def run_integration_tests(verbose=False):
    """Run integration tests."""
    cmd = ['python', '-m', 'pytest', 'tests/integration/']
    
    if verbose:
        cmd.append('-v')
    
    cmd.append('-m')
    cmd.append('integration')
    
    return run_command(cmd, "Integration Tests")


def run_all_tests(verbose=False, coverage=False):
    """Run all tests."""
    cmd = ['python', '-m', 'pytest', 'tests/']
    
    if verbose:
        cmd.append('-v')
    
    if coverage:
        cmd.extend(['--cov=src', '--cov-report=html', '--cov-report=term-missing'])
    
    return run_command(cmd, "All Tests")


def run_specific_test(test_path, verbose=False):
    """Run a specific test file or test method."""
    cmd = ['python', '-m', 'pytest', test_path]
    
    if verbose:
        cmd.append('-v')
    
    return run_command(cmd, f"Specific Test: {test_path}")


def run_linting():
    """Run code linting."""
    success = True
    
    # Run flake8
    cmd = ['flake8', 'src/', 'main.py', '--max-line-length=100']
    if not run_command(cmd, "Linting with flake8"):
        success = False
    
    # Run pylint
    cmd = ['pylint', 'src/', 'main.py', '--disable=C0103,R0903,R0913']
    if not run_command(cmd, "Linting with pylint"):
        success = False
    
    return success


def check_dependencies():
    """Check if all test dependencies are installed."""
    required_packages = [
        'pytest', 'pytest-cov', 'pytest-mock', 'mock', 
        'parameterized', 'flake8', 'pylint'
    ]
    
    missing_packages = []
    
    for package in required_packages:
        try:
            __import__(package.replace('-', '_'))
        except ImportError:
            missing_packages.append(package)
    
    if missing_packages:
        print("Missing test dependencies:")
        for package in missing_packages:
            print(f"  - {package}")
        print("\nInstall missing dependencies with:")
        print("pip install -r requirements-test.txt")
        return False
    
    print("All test dependencies are installed.")
    return True


def run_performance_tests():
    """Run performance/slow tests."""
    cmd = ['python', '-m', 'pytest', 'tests/', '-m', 'slow', '-v']
    return run_command(cmd, "Performance Tests")


def generate_test_report():
    """Generate comprehensive test report."""
    print("Generating comprehensive test report...")
    
    # Run all tests with coverage
    cmd = [
        'python', '-m', 'pytest', 'tests/',
        '--cov=src',
        '--cov-report=html:htmlcov',
        '--cov-report=xml:coverage.xml',
        '--cov-report=term-missing',
        '--junit-xml=test-results.xml',
        '-v'
    ]
    
    success = run_command(cmd, "Comprehensive Test Report")
    
    if success:
        print("\nTest reports generated:")
        print("  - HTML Coverage Report: htmlcov/index.html")
        print("  - XML Coverage Report: coverage.xml")
        print("  - JUnit Test Results: test-results.xml")
    
    return success


def main():
    """Main test runner function."""
    parser = argparse.ArgumentParser(description='VLAN Cleanup Automation Test Runner')
    parser.add_argument('--unit', action='store_true', help='Run unit tests')
    parser.add_argument('--integration', action='store_true', help='Run integration tests')
    parser.add_argument('--all', action='store_true', help='Run all tests')
    parser.add_argument('--lint', action='store_true', help='Run code linting')
    parser.add_argument('--performance', action='store_true', help='Run performance tests')
    parser.add_argument('--report', action='store_true', help='Generate comprehensive test report')
    parser.add_argument('--check-deps', action='store_true', help='Check test dependencies')
    parser.add_argument('--test', type=str, help='Run specific test file or method')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')
    parser.add_argument('--coverage', '-c', action='store_true', help='Generate coverage report')
    
    args = parser.parse_args()
    
    # If no specific action is specified, run all tests
    if not any([args.unit, args.integration, args.all, args.lint, 
                args.performance, args.report, args.check_deps, args.test]):
        args.all = True
    
    success = True
    
    # Check dependencies first
    if args.check_deps:
        return 0 if check_dependencies() else 1
    
    # Ensure we're in the right directory
    if not Path('tests').exists():
        print("ERROR: tests directory not found. Run this script from the project root.")
        return 1
    
    # Run tests based on arguments
    if args.test:
        success &= run_specific_test(args.test, args.verbose)
    
    if args.unit:
        success &= run_unit_tests(args.verbose, args.coverage)
    
    if args.integration:
        success &= run_integration_tests(args.verbose)
    
    if args.all:
        success &= run_all_tests(args.verbose, args.coverage)
    
    if args.lint:
        success &= run_linting()
    
    if args.performance:
        success &= run_performance_tests()
    
    if args.report:
        success &= generate_test_report()
    
    # Print summary
    print(f"\n{'='*60}")
    if success:
        print("✅ ALL TESTS PASSED!")
    else:
        print("❌ SOME TESTS FAILED!")
    print('='*60)
    
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
