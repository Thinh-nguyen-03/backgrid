# Benchmarks

Hardware: 4 vCPU, 16 GB RAM, NVMe SSD (local dev)

## Targets
- Worker throughput ≥ 10 jobs/sec (1y daily bars, 1 symbol)
- P95 job latency ≤ 2 s
- Portfolio optimization ≤ 500 ms (HRP, 10–20 assets)

## Methodology
- Use cached Parquet to eliminate network variance
- Submit 1k parameterized jobs; record medians and p95
- Repeat 5 runs; report average of medians

## Sample Results
| Scenario | Throughput (jobs/s) | P95 Latency (s) |
|---|---:|---:|
| 1y daily, MA cross | 12.4 | 1.7 |
| 5y daily, MA cross | 7.6 | 3.8 |
| 25 symbols portfolio HRP | 3.2 | 0.46 |
