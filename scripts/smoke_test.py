"""
Smoke test script for Backgrid API (Phase 1)

Usage:
    1. Start the API server: python src/api.py
    2. Run this script: python scripts/smoke_test.py
"""

import requests
import time
import sys
from typing import Dict, Any


BASE_URL = "http://localhost:8000"


def print_test(name: str):
    """Print test name"""
    print(f"\n{'='*60}")
    print(f"TEST: {name}")
    print('='*60)


def print_success(message: str):
    """Print success message"""
    print(f"✅ {message}")


def print_error(message: str):
    """Print error message"""
    print(f"❌ {message}")


def print_result(result: Dict[str, Any]):
    """Print formatted result"""
    for key, value in result.items():
        if key == "equity_curve":
            print(f"  {key}: [{len(value)} data points]")
        else:
            print(f"  {key}: {value}")


def test_health_check() -> bool:
    """Test health check endpoint"""
    print_test("Health Check")

    try:
        response = requests.get(f"{BASE_URL}/api/v1/health")

        if response.status_code == 200:
            data = response.json()
            print_success("Health check passed")
            print_result(data)
            return True
        else:
            print_error(f"Health check failed with status {response.status_code}")
            return False

    except Exception as e:
        print_error(f"Health check failed: {str(e)}")
        print("💡 Make sure the API server is running: python src/api.py")
        return False


def test_submit_job() -> Dict[str, Any]:
    """Test job submission"""
    print_test("Submit Backtest Job (AAPL 2023)")

    payload = {
        "symbol": "AAPL",
        "strategy": "ma_crossover",
        "params": {"fast": 10, "slow": 30},
        "start": "2023-01-01",
        "end": "2023-12-31"
    }

    try:
        print("📤 Submitting backtest job...")
        start_time = time.time()

        response = requests.post(
            f"{BASE_URL}/api/v1/jobs",
            json=payload,
            timeout=30
        )

        elapsed = time.time() - start_time

        if response.status_code == 200:
            data = response.json()
            print_success(f"Job completed in {elapsed:.2f}s")
            print_result(data)
            return data
        else:
            print_error(f"Job submission failed with status {response.status_code}")
            print(f"Response: {response.text}")
            return None

    except requests.exceptions.Timeout:
        print_error("Request timed out (>30s)")
        return None
    except Exception as e:
        print_error(f"Job submission failed: {str(e)}")
        return None


def test_get_job(job_id: str) -> bool:
    """Test job retrieval"""
    print_test(f"Retrieve Job Results ({job_id})")

    try:
        response = requests.get(f"{BASE_URL}/api/v1/jobs/{job_id}")

        if response.status_code == 200:
            data = response.json()
            print_success("Job retrieved successfully")
            print_result(data)
            return True
        else:
            print_error(f"Job retrieval failed with status {response.status_code}")
            return False

    except Exception as e:
        print_error(f"Job retrieval failed: {str(e)}")
        return False


def test_invalid_symbol() -> bool:
    """Test error handling with invalid symbol"""
    print_test("Error Handling (Invalid Symbol)")

    payload = {
        "symbol": "INVALIDXYZ123",
        "strategy": "ma_crossover",
        "start": "2023-01-01"
    }

    try:
        response = requests.post(f"{BASE_URL}/api/v1/jobs", json=payload)

        if response.status_code == 400:
            error_data = response.json()
            print_success("Error handled correctly (400 Bad Request)")
            print(f"  Error message: {error_data.get('error', 'N/A')}")
            return True
        else:
            print_error(f"Expected 400, got {response.status_code}")
            return False

    except Exception as e:
        print_error(f"Error handling test failed: {str(e)}")
        return False


def test_invalid_params() -> bool:
    """Test validation with invalid parameters"""
    print_test("Parameter Validation (fast >= slow)")

    payload = {
        "symbol": "AAPL",
        "strategy": "ma_crossover",
        "params": {"fast": 30, "slow": 10},  # Invalid: fast >= slow
        "start": "2023-01-01"
    }

    try:
        response = requests.post(f"{BASE_URL}/api/v1/jobs", json=payload)

        if response.status_code == 422:
            print_success("Validation error handled correctly (422)")
            return True
        else:
            print_error(f"Expected 422, got {response.status_code}")
            return False

    except Exception as e:
        print_error(f"Validation test failed: {str(e)}")
        return False


def run_all_tests():
    """Run all smoke tests"""
    print("\n" + "="*60)
    print("BACKGRID PHASE 1 SMOKE TESTS")
    print("="*60)

    results = []

    # Test 1: Health check
    results.append(("Health Check", test_health_check()))

    # Test 2: Submit job
    job_data = test_submit_job()
    results.append(("Submit Job", job_data is not None))

    # Test 3: Retrieve job (only if submission succeeded)
    if job_data:
        job_id = job_data.get("job_id")
        results.append(("Retrieve Job", test_get_job(job_id)))
    else:
        results.append(("Retrieve Job", False))

    # Test 4: Error handling
    results.append(("Invalid Symbol", test_invalid_symbol()))

    # Test 5: Validation
    results.append(("Invalid Params", test_invalid_params()))

    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {name}")

    print("\n" + "="*60)
    print(f"RESULTS: {passed}/{total} tests passed")
    print("="*60)

    # Exit code
    sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    run_all_tests()
