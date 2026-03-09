# Memory Drift Benchmark — Baseline Numbers (27 scenarios)

**Run:** `py -3 drift_benchmark.py --all`  
**Date:** Stage 1 summary run.

---

## Summary

| Metric | Value |
|--------|-------|
| **Scenarios** | 27 |
| **Baseline A (全历史) 平均** | 0.94 |
| **Baseline B (最近 N 轮) 平均** | 0.88 |
| **Baseline C (先摘要再答) 平均** | 0.94 |
| **Guard 平均** | 0.94 |
| **Guard 更优次数** | 6 / 27 |
| **guard_win_rate** | 0.22 |
| **检测到 drift 次数** | 8 / 27 |
| **drift_detection_rate** | 0.30 |
| **latest_state_accuracy** | 0.94 |
| **constraint_violation_count** | 10 |
| **stale_reference_count** | 7 |

---

## Interpretation

- **Baseline B** is weakest (0.88), as expected when context is truncated.
- **A, C, Guard** all at 0.94 on average; Guard wins in 6 scenarios (e.g. 02, 08, 09, 11, 12, 20) where drift is detected or Baselines drop.
- These numbers serve as **project baseline** for future model/scenario changes.
