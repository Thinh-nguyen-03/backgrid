import requests
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict
import statistics

BASE_URL = "http://localhost:8000"

def submit_single_job(job_num: int) -> Dict:
    """Submit a single backtest job and measure time"""
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

        return {
            "job_num": job_num,
            "status_code": response.status_code,
            "elapsed": elapsed,
            "success": response.status_code == 200,
            "timed_out": False
        }
    except requests.exceptions.Timeout:
        elapsed = time.time() - start
        return {
            "job_num": job_num,
            "status_code": None,
            "elapsed": elapsed,
            "success": False,
            "timed_out": True
        }
    except Exception as e:
        elapsed = time.time() - start
        return {
            "job_num": job_num,
            "status_code": None,
            "elapsed": elapsed,
            "success": False,
            "error": str(e),
            "timed_out": False
        }

def test_sequential(num_jobs: int = 10):
    """Test sequential execution"""
    print("\n" + "="*60)
    print(f"SEQUENTIAL TEST: {num_jobs} jobs")
    print("="*60)

    results = []
    start_time = time.time()

    for i in range(num_jobs):
        print(f"Submitting job {i+1}/{num_jobs}...")
        result = submit_single_job(i)
        results.append(result)

        if result["success"]:
            print(f"  [PASS] Job {i+1}: {result['elapsed']:.2f}s")
        elif result["timed_out"]:
            print(f"  [TIMEOUT] Job {i+1}")
        else:
            print(f"  [FAIL] Job {i+1}")

    total_time = time.time() - start_time

    print_results(results, total_time, "Sequential")
    return results, total_time

def test_concurrent(num_jobs: int = 10, max_workers: int = 5):
    """Test concurrent execution"""
    print("\n" + "="*60)
    print(f"CONCURRENT TEST: {num_jobs} jobs with {max_workers} workers")
    print("="*60)

    results = []
    start_time = time.time()

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(submit_single_job, i): i for i in range(num_jobs)}

        for future in as_completed(futures):
            job_num = futures[future]
            result = future.result()
            results.append(result)

            if result["success"]:
                print(f"  [PASS] Job {job_num+1}: {result['elapsed']:.2f}s")
            elif result["timed_out"]:
                print(f"  [TIMEOUT] Job {job_num+1}")
            else:
                print(f"  [FAIL] Job {job_num+1}")

    total_time = time.time() - start_time

    print_results(results, total_time, "Concurrent")
    return results, total_time

def print_results(results: List[Dict], total_time: float, test_type: str):
    """Print benchmark results"""
    successful = [r for r in results if r["success"]]
    timeouts = [r for r in results if r["timed_out"]]
    failed = [r for r in results if not r["success"] and not r["timed_out"]]

    print(f"\nRESULTS ({test_type})")
    print(f"Total jobs:       {len(results)}")
    print(f"Successful:       {len(successful)}")
    print(f"Timeouts (>60s):  {len(timeouts)}")
    print(f"Failed:           {len(failed)}")
    print(f"\nTotal time:       {total_time:.2f}s")
    print(f"Throughput:       {len(results)/total_time:.2f} jobs/sec")

    if successful:
        latencies = [r["elapsed"] for r in successful]
        print(f"\nPer-job latency:")
        print(f"  Min:     {min(latencies):.2f}s")
        print(f"  Max:     {max(latencies):.2f}s")
        print(f"  Avg:     {statistics.mean(latencies):.2f}s")
        print(f"  Median:  {statistics.median(latencies):.2f}s")

def print_decision_gate():
    """Print decision gate analysis"""
    print("\nDECISION GATE ANALYSIS")
    print("Phase 2 is needed if ANY of these are true:")
    print("1. Timeouts >30s occurring regularly")
    print("2. Throughput <5 jobs/sec with concurrent users")
    print("3. API blocking prevents multiple concurrent users")
    print("\nRecommendation based on results:")


def main():
    print("\nPHASE 1 BOTTLENECK BENCHMARK")
    print("\nThis benchmark tests if Phase 1 needs async workers.")
    print("Make sure the API is running: python src/api.py")
    print("Press Enter to continue.")
    input()

    # Test 1: Sequential baseline
    seq_results, seq_time = test_sequential(num_jobs=10)

    # Test 2: Concurrent (simulates multiple users)
    conc_results, conc_time = test_concurrent(num_jobs=10, max_workers=5)

    # Analysis
    print_decision_gate()

    seq_throughput = len(seq_results) / seq_time
    conc_throughput = len(conc_results) / conc_time

    seq_timeouts = sum(1 for r in seq_results if r.get("timed_out"))
    conc_timeouts = sum(1 for r in conc_results if r.get("timed_out"))

    needs_phase2 = False
    reasons = []

    if seq_timeouts > 0 or conc_timeouts > 0:
        needs_phase2 = True
        reasons.append(f"Timeouts detected ({seq_timeouts + conc_timeouts} total)")

    if conc_throughput < 5:
        needs_phase2 = True
        reasons.append(f"Throughput below 5 jobs/sec ({conc_throughput:.2f})")

    if conc_time > seq_time * 1.2:
        needs_phase2 = True
        reasons.append(f"Concurrent execution blocked (slower than sequential)")

    if needs_phase2:
        print("\n[ACTION REQUIRED] Phase 2 is NEEDED")
        print("\nReasons:")
        for reason in reasons:
            print(f"  - {reason}")
        print("\nNext steps:")
        print("1. Document these results in docs/DECISION_LOG.md")
        print("2. Implement Phase 2 (Celery + Redis + PostgreSQL)")
    else:
        print("\n[OK] Phase 1 is still sufficient")
        print("\nPhase 1 performance is acceptable:")
        print(f"  - Sequential throughput: {seq_throughput:.2f} jobs/sec")
        print(f"  - Concurrent throughput: {conc_throughput:.2f} jobs/sec")
        print(f"  - No timeouts detected")
        print("\nStay in Phase 1 until measurements show otherwise.")

    print("="*60)

if __name__ == "__main__":
    main()
