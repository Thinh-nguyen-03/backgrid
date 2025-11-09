# Scripts Directory

This directory contains utility scripts for testing and running Backgrid.

## Smoke Test Script

**Purpose:** Quick end-to-end test of the API to verify basic functionality.

**Usage:**

1. Start the API server in one terminal:
   ```bash
   python src/api.py
   ```

2. Run the smoke test in another terminal:
   ```bash
   python scripts/smoke_test.py
   ```

**What it tests:**
- ✅ Health check endpoint
- ✅ Job submission (AAPL backtest)
- ✅ Job retrieval
- ✅ Error handling (invalid symbol)
- ✅ Validation (invalid parameters)

**Expected output:**
```
============================================================
BACKGRID PHASE 1 SMOKE TESTS
============================================================

============================================================
TEST: Health Check
============================================================
✅ Health check passed
  status: ok
  phase: 1
  ...

============================================================
TEST SUMMARY
============================================================
✅ PASS: Health Check
✅ PASS: Submit Job
✅ PASS: Retrieve Job
✅ PASS: Invalid Symbol
✅ PASS: Invalid Params

============================================================
RESULTS: 5/5 tests passed
============================================================
```

## Adding New Scripts

When adding new scripts to this directory:
1. Use descriptive filenames (e.g., `benchmark_performance.py`)
2. Add usage instructions at the top of the file
3. Update this README with a description
