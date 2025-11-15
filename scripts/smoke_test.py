import requests
import time
import sys
from typing import Dict, Any

BASE_URL = "http://localhost:8000"

def print_test(name: str):
    print(f"\nTEST: {name}")

def print_success(message: str):
    print(f"[PASS] {message}")


def print_error(message: str):
    print(f"[FAIL] {message}")

def print_result(result: Dict[str, Any]):
    for key, value in result.items():
        if key == "equity_curve":
            print(f"  {key}: [{len(value)} data points]")
        else:
            print(f"  {key}: {value}")


def test_health_check() -> bool:
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
        print("NOTE: Make sure the API server is running: python src/api.py")
        return False


def test_submit_job() -> Dict[str, Any]:
    print_test("Submit Backtest Job (AAPL 2023)")

    payload = {
        "symbol": "AAPL",
        "strategy": "ma_crossover",
        "params": {"fast": 10, "slow": 30},
        "start": "2023-01-01",
        "end": "2023-12-31"
    }

    try:
        print("Submitting backtest job")
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
    print_test("Error Handling (Invalid Symbol)")

    payload = {
        "symbol": "INVALID@SYMBOL",
        "strategy": "ma_crossover",
        "start": "2023-01-01"
    }

    try:
        response = requests.post(f"{BASE_URL}/api/v1/jobs", json=payload)

        if response.status_code in [400, 422]:
            error_data = response.json()
            print_success(f"Error handled correctly ({response.status_code})")
            print(f"  Error message: {error_data.get('error', error_data.get('detail', 'N/A'))}")
            return True
        else:
            print_error(f"Expected 400 or 422, got {response.status_code}")
            return False

    except Exception as e:
        print_error(f"Error handling test failed: {str(e)}")
        return False


def test_invalid_params() -> bool:
    print_test("Parameter Validation (fast >= slow)")

    payload = {
        "symbol": "AAPL",
        "strategy": "ma_crossover",
        "params": {"fast": 30, "slow": 10},
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
    print("BACKGRID SMOKE TESTS")

    results = []

    results.append(("Health Check", test_health_check()))
    job_data = test_submit_job()
    results.append(("Submit Job", job_data is not None))

    if job_data:
        job_id = job_data.get("job_id")
        results.append(("Retrieve Job", test_get_job(job_id)))
    else:
        results.append(("Retrieve Job", False))

    results.append(("Invalid Symbol", test_invalid_symbol()))

    results.append(("Invalid Params", test_invalid_params()))

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = "[PASS]" if result else "[FAIL]"
        print(f"{status}: {name}")

    print(f"RESULTS: {passed}/{total} tests passed")

    sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    run_all_tests()
