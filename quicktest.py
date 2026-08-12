#!/usr/bin/env python
"""
Usage:
$ uv sync
$ source .venv/bin/activate

# To run entire test suite
$ python quicktest.py

# Run specific tests
$ python quicktest.py -v 2 tests.<your_test_1> tests.<your_test_2>
"""

import argparse
import os
import sys

import django
from django.test.runner import DiscoverRunner

if __name__ == "__main__":
    """
    Parse which tests the user wants to run with what verbosity
    and run them via a custom test runner.
    """
    parser = argparse.ArgumentParser(usage="[args]", description="Run Django tests.")
    parser.add_argument("tests", nargs="*", type=str, default=".")
    parser.add_argument("--verbosity", "-v", nargs="?", type=int, default=1)
    args = parser.parse_args()

    print(f"Running tests using Django version {django.get_version()}...")
    os.environ["DJANGO_SETTINGS_MODULE"] = "tests.test_settings"
    django.setup()
    test_runner = DiscoverRunner(verbosity=args.verbosity)
    failures = test_runner.run_tests(args.tests)
    sys.exit(bool(failures))
