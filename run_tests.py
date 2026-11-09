"""
Test runner that works in this Windows/cmd environment.
Run with: python run_tests.py
"""
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

# Discover and run all tests
loader = unittest.TestLoader()
suite = loader.discover(str(PROJECT_ROOT / "tests"), pattern="test_*.py")
runner = unittest.TextTestRunner(verbosity=2)
result = runner.run(suite)

# Exit with appropriate code
sys.exit(0 if result.wasSuccessful() else 1)
