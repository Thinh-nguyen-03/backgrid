import requests
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
import statistics

BASE_URL = "http://localhost:8000"

def simulate_user(user_id: int, num_requests: int = 3):
    """Simulate a single user making multiple requests"""
    print(f"User {user_id}: Starting {num_requests} requests...")

    user_results = []
    for i in range(num_requests):
        start = time.time()

        try:
            response = requests.post(
                f"{BASE_URL}/api/v1/jobs",
                json={
                    "symbol": "AAPL",
                    "strategy": "ma_crossover",
                    "params": {"fast": 10, "slow": 30},
                    "start": "2023-01-01",
                    "end": "2023-12-31"
                },
                timeout=60
            )
            elapsed = time.time() - start

            user_results.append({
                "user_id": user_id,
                "request_num": i,
                "elapsed": elapsed,
                "success": response.status_code == 200
            })

            status = "[PASS]" if response.status_code == 200 else "[FAIL]"
            print(f"User {user_id} request {i+1}: {status} {elapsed:.2f}s")

        except Exception as e:
            elapsed = time.time() - start
            user_results.append({
                "user_id": user_id,
                "request_num": i,
                "elapsed": elapsed,
                "success": False,
                "error": str(e)
            })
            print(f"User {user_id} request {i+1}: [ERROR] {str(e)}")

    return user_results

def test_concurrent_users(num_users: int = 5, requests_per_user: int = 3):
    """Test multiple concurrent users"""
    print(f"\nCONCURRENT USERS TEST: {num_users} users, {requests_per_user} requests each")

    all_results = []
    start_time = time.time()

    with ThreadPoolExecutor(max_workers=num_users) as executor:
        futures = {
            executor.submit(simulate_user, user_id, requests_per_user): user_id
            for user_id in range(num_users)
        }

        for future in as_completed(futures):
            user_results = future.result()
            all_results.extend(user_results)

    total_time = time.time() - start_time

    # Analysis
    print("\nRESULTS")

    total_requests = len(all_results)
    successful = sum(1 for r in all_results if r["success"])
    failed = total_requests - successful

    print(f"Total requests:   {total_requests}")
    print(f"Successful:       {successful}")
    print(f"Failed:           {failed}")
    print(f"\nTotal time:       {total_time:.2f}s")
    print(f"Throughput:       {total_requests/total_time:.2f} requests/sec")

    if successful > 0:
        latencies = [r["elapsed"] for r in all_results if r["success"]]
        print(f"\nRequest latency:")
        print(f"  Min:     {min(latencies):.2f}s")
        print(f"  Max:     {max(latencies):.2f}s")
        print(f"  Avg:     {statistics.mean(latencies):.2f}s")
        print(f"  Median:  {statistics.median(latencies):.2f}s")

        # Check if concurrent execution is actually parallel
        avg_latency = statistics.mean(latencies)
        expected_sequential_time = avg_latency * total_requests
        parallelism_ratio = expected_sequential_time / total_time

        print(f"\nParallelism analysis:")
        print(f"  Expected (sequential): {expected_sequential_time:.2f}s")
        print(f"  Actual (concurrent):   {total_time:.2f}s")
        print(f"  Speedup factor:        {parallelism_ratio:.2f}x")

        if parallelism_ratio < 1.5:
            print(f"\n  [WARNING] Low parallelism - API is blocking!")
            print(f"  Concurrent execution only {parallelism_ratio:.1f}x faster than sequential.")
            return False
        else:
            print(f"\n  [OK] Good parallelism detected")
            return True

    return successful > 0

def main():
    print("\nCONCURRENT USERS BENCHMARK")
    print("\nSimulates multiple users making requests simultaneously.")
    print("Phase 2 needed if API blocks concurrent requests.")
    print("\nMake sure API is running: python src/api.py")
    print("Press Enter to continue.")
    input()

    # Test with increasing concurrency
    test_cases = [
        (3, 2),   # 3 users, 2 requests each = 6 total
        (5, 3),   # 5 users, 3 requests each = 15 total
        (10, 2),  # 10 users, 2 requests each = 20 total
    ]

    results = []
    for num_users, requests_per_user in test_cases:
        can_handle = test_concurrent_users(num_users, requests_per_user)
        results.append((num_users, can_handle))
        time.sleep(2)  # Brief pause between tests

    print("\nFINAL ANALYSIS")

    failures = sum(1 for _, can_handle in results if not can_handle)

    if failures > 0:
        print("\n[ACTION REQUIRED] Phase 2 is NEEDED")
        print(f"\nAPI blocked with concurrent users in {failures}/{len(results)} tests.")
        print("Synchronous execution prevents true concurrency.")
        print("\nNext steps:")
        print("1. Document these results in docs/DECISION_LOG.md")
        print("2. Implement Phase 2 (async workers with Celery)")
    else:
        print("\n[OK] Phase 1 handles concurrent users adequately")
        print("Current implementation supports multiple concurrent users.")

if __name__ == "__main__":
    main()
