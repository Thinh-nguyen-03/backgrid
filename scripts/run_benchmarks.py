import sys
import time
import subprocess
from datetime import datetime

def print_header(title):
    print(title.center(60))

def run_benchmark(script_name, description):
    """Run a benchmark script and return exit code"""
    print_header(f"Running: {description}")
    print(f"\nScript: {script_name}")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    try:
        result = subprocess.run(
            [sys.executable, script_name],
            cwd=".",
            capture_output=False,
            text=True
        )
        return result.returncode
    except Exception as e:
        print(f"[ERROR] Failed to run {script_name}: {str(e)}")
        return 1

def generate_decision_report(results):
    """Generate decision report based on benchmark results"""
    print_header("DECISION REPORT")

    total_tests = len(results)
    passed = sum(1 for _, code in results if code == 0)
    failed = total_tests - passed

    print(f"\nBenchmark Summary:")
    print(f"  Total tests: {total_tests}")
    print(f"  Passed:      {passed}")
    print(f"  Failed:      {failed}")

    print(f"\nIndividual Results:")
    for name, code in results:
        status = "[PASS]" if code == 0 else "[FAIL]"
        print(f"  {status} {name}")

    print("\nDECISION GATE")
    # Any benchmark failure indicates need for Phase 2
    if failed > 0:
        print("\n[ACTION REQUIRED] Proceed to Phase 2")
        print("\nEvidence:")
        print("  Phase 1 bottleneck detected in one or more tests:")
        for name, code in results:
            if code != 0:
                print(f"    - {name}")

        print("\nNext Steps:")
        print("  1. Copy benchmark outputs to docs/DECISION_LOG.md")
        print("  2. Create decision entry using template in DECISION_LOG.md")
        print("  3. Implement Phase 2: Celery + Redis + PostgreSQL")
        print("  4. Re-run benchmarks to verify improvement")

        print("\nTemplate for DECISION_LOG.md:")
        print(f"""
## Decision: Add Celery + Redis (Date: {datetime.now().strftime('%Y-%m-%d')})

### Problem
[Copy benchmark results showing bottleneck]

### Evidence
```
[Paste benchmark outputs here]
```

### Alternatives Considered
1. **Stay in Phase 1**: Not viable, measurements show bottleneck
2. **ThreadPoolExecutor**: Python GIL limits concurrency
3. **Celery + Redis**: Battle-tested, true async execution

### Decision
Implement Phase 2 with Celery workers and Redis queue.

### Expected Impact
- Throughput: >10 jobs/sec (from current <5 jobs/sec)
- API response: <100ms (non-blocking)
- Concurrent users: Support 10+ simultaneous users
""")

    else:
        print("\n[OK] Stay in Phase 1")
        print("\nAll benchmarks passed.")
        print("Phase 1 synchronous execution is sufficient.")
        print("\nNo action needed - continue with Phase 1 until")
        print("measurements show a bottleneck.")

def main():
    print_header("PHASE 1 BOTTLENECK BENCHMARK SUITE")

    print("""
This suite determines if Phase 2 (async workers) is needed.

Tests run:
  1. Throughput - Can we handle >5 jobs/sec?
  2. Timeouts - Do jobs exceed 30s threshold?
  3. Concurrent Users - Does API block with multiple users?

Prerequisites:
  - API must be running: python src/api.py
  - Clean state (no pending jobs)

Press Enter to start.
""")
    input()

    # Run all benchmarks
    benchmarks = [
        ("scripts/benchmark_throughput.py", "Throughput Test"),
        ("scripts/benchmark_timeout.py", "Timeout Test"),
        ("scripts/benchmark_concurrent.py", "Concurrent Users Test"),
    ]

    results = []
    for script, description in benchmarks:
        code = run_benchmark(script, description)
        results.append((description, code))
        time.sleep(2)  # Brief pause between benchmarks

    # Generate decision report
    generate_decision_report(results)

if __name__ == "__main__":
    main()
