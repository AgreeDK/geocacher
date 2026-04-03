import pytest
import sys

def run():
    """
    Entry point for 'opensak-test'.
    Runs all tests found in the /tests directory.
    """
    args = ["tests"] + sys.argv[1:]
    
    # Run pytest and exit with its return code
    print(f"OpenSAK Test Suite")
    sys.exit(pytest.main(args))