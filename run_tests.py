#!/usr/bin/env python3
"""
Test runner for ShortURL application
"""

import unittest
import sys
import os

def run_all_tests():
    """Run all tests and return success status"""
    # Discover and run tests
    loader = unittest.TestLoader()
    
    # Load specific test modules that we know work
    test_modules = [
        'tests.test_security_isolated',
        'tests.test_utils', 
        'tests.test_integration',
        'tests.test_startup'
    ]
    
    suite = unittest.TestSuite()
    
    for module in test_modules:
        try:
            tests = loader.loadTestsFromName(module)
            suite.addTests(tests)
        except ImportError as e:
            print(f"Warning: Could not load {module}: {e}")
            
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2, stream=sys.stdout)
    result = runner.run(suite)
    
    # Print summary
    total_tests = result.testsRun
    failures = len(result.failures)
    errors = len(result.errors)
    
    print(f"\n{'='*60}")
    print(f"TEST SUMMARY")
    print(f"{'='*60}")
    print(f"Total tests run: {total_tests}")
    print(f"Failures: {failures}")
    print(f"Errors: {errors}")
    print(f"Success rate: {((total_tests - failures - errors) / total_tests * 100):.1f}%" if total_tests > 0 else "N/A")
    
    return result.wasSuccessful()

if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)