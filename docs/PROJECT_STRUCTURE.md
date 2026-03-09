# Memory Guard — 项目结构

给外部测试用户看的目录说明。

---

## 核心代码

| 文件 | 作用 |
|------|------|
| `memoryguard.py` | CLI 入口：prepare / check / run / benchmark / analyze |
| `cursor_guard_experiment.py` | Cursor Guard 实验：state injection、drift check |
| `extractor.py` | 从对话中提取结构化事件 |
| `memory_guard.py` | 检测 update / conflict |
| `state_builder.py` | 从 events + findings 构建 current state |

---

## Benchmark

| 文件/目录 | 作用 |
|-----------|------|
| `drift_benchmark.py` | Memory Drift Benchmark（4 条路径，30 个 scenario） |
| `scenarios/` | drift_scenario_01.json … drift_scenario_30.json |
| `scenarios/scenario_taxonomy.md` | 场景 taxonomy（含 temporal drift） |

---

## Session / 输出

| 文件/目录 | 作用 |
|-----------|------|
| `cursor_sessions/session_real_20plus.json` | **官方 demo**（28 轮待办、负责人变更、喵约束） |
| `cursor_sessions/session_01.json` | 示例 session |
| `outputs/` | 模型输出、benchmark 结果、events.json |

---

## 文档

| 文件 | 作用 |
|------|------|
| `README.md` | 项目说明、Quickstart、命令 |
| `TEST_WITH_FRIENDS.md` | **给测试用户**：怎么测、要什么反馈 |
| `STAGE1_SUMMARY.md` | Stage 1 总结（Problem / Approach / Evaluation / Prototype） |
| `BASELINE_NUMBERS.md` | 27/30 scenario 的 baseline 数字 |
| `REAL_SESSION_DEMO.md` | 真实 session 演示说明 |
| `PLAN_NEXT_PHASE.md` | 下一阶段计划 |
| `docs/PROJECT_STRUCTURE.md` | 本文件 |
