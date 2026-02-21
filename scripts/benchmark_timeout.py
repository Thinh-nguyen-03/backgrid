import requests
import time

BASE_URL = "http://localhost:8000"

def test_long_backtest(symbol: str, years: int, timeout: int = 35):
    """Test a long backtest that might timeout"""
    print(f"\nTesting {symbol} for {years} years (timeout={timeout}s)...")

    start_year = 2024 - years
    payload = {
        "symbol": symbol,
        "strategy": "ma_crossover",
        "params": {"fast": 10, "slow": 30},
        "start": f"{start_year}-01-01",
        "end": "2023-12-31"
    }

    start = time.time()

    try:
        response = requests.post(
            f"{BASE_URL}/api/v1/jobs",
            json=payload,
            timeout=timeout
        )
        elapsed = time.time() - start

        if response.status_code == 200:
            print(f"  [PASS] Completed in {elapsed:.2f}s")
            return {"success": True, "elapsed": elapsed, "timed_out": False}
        else:
            print(f"  [FAIL] Status {response.status_code}")
            return {"success": False, "elapsed": elapsed, "timed_out": False}

    except requests.exceptions.Timeout:
        elapsed = time.time() - start
        print(f"  [TIMEOUT] Exceeded {timeout}s threshold")
        return {"success": False, "elapsed": elapsed, "timed_out": True}

    except Exception as e:
        elapsed = time.time() - start
        print(f"  [ERROR] {str(e)}")
        return {"success": False, "elapsed": elapsed, "error": str(e)}

def main():
    print("\nHTTP TIMEOUT BENCHMARK")
    print("\nTesting if backtests exceed 30s timeout threshold.")
    print("Phase 2 needed if timeouts occur regularly.")
    print("\nMake sure API is running: python src/api.py")
    print("Press Enter to continue.")
    input()

    tests = [
        ("AAPL", 1, 35),   # 1 year - should pass
        ("AAPL", 3, 35),   # 3 years - might timeout
        ("AAPL", 5, 35),   # 5 years - likely timeout
    ]

    results = []
    for symbol, years, timeout in tests:
        result = test_long_backtest(symbol, years, timeout)
        results.append((symbol, years, result))

    print("\nRESULTS")

    timeouts = sum(1 for _, _, r in results if r.get("timed_out"))
    successful = sum(1 for _, _, r in results if r.get("success"))

    print(f"Total tests:  {len(results)}")
    print(f"Successful:   {successful}")
    print(f"Timeouts:     {timeouts}")

    if timeouts > 0:
        print("\n[ACTION REQUIRED] Phase 2 is NEEDED")
        print(f"\n{timeouts} job(s) exceeded 30s threshold.")
        print("Synchronous execution is blocking for too long.")
        print("\nNext steps:")
        print("1. Document these timeout results in docs/DECISION_LOG.md")
        print("2. Implement Phase 2 (async workers)")
    else:
        print("\n[OK] No timeouts detected")
        print("Phase 1 synchronous execution is fast enough.")

if __name__ == "__main__":
    main()
