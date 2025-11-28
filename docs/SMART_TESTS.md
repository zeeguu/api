# Smart Test Runner

This project now includes `pytest-testmon` for intelligent test selection. It tracks which tests execute which parts of your code and only runs tests affected by your changes.

## Usage

### Smart Testing (Default)
Run only tests affected by code changes:
```bash
./run_tests.sh
```

### Full Test Suite
Run all tests (two options):
```bash
# Option 1: Use the --full flag
./run_tests.sh --full
# or
./run_tests.sh -f

# Option 2: Use the dedicated full test script
./run_tests_full.sh
```

### Reset Cache
Delete the cache and rebuild from scratch:
```bash
./run_tests.sh --nocache
```

### Pass Additional pytest Arguments
Any pytest arguments can be passed through:
```bash
./run_tests.sh -v  # verbose output
./run_tests.sh -k test_user  # run only tests matching "test_user"
./run_tests.sh --full -v  # full run with verbose output
```

## How It Works

On the first run, pytest-testmon builds a database (`.testmondata`) that tracks:
- Which tests execute which code files
- Code coverage information
- Dependencies between tests and source files

On subsequent runs, it:
1. Detects which files have changed since last run
2. Determines which tests might be affected
3. Runs only those tests

This dramatically speeds up your development workflow while maintaining confidence that affected tests are run.

## When to Use Full Runs

Use `--full` periodically or when:
- After major refactoring
- Before pushing to remote
- When test results seem inconsistent
- After pulling major changes from others

## Full Test Runner (Without Testmon)

The original full test runner is still available if you need to run all tests without testmon:
```bash
./run_tests_full.sh  # Runs all tests without testmon
```
