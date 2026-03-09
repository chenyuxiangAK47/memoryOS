# Memory Guard / Memory Drift Benchmark — 下一阶段修改计划

> 依据「发给 Cursor 的整合指令」整理，便于砍优先级与跟踪。

---

## 当前状态小结

- **已有**：事件提取、Memory Guard（update/conflict）、state_builder、drift_benchmark（A/B/C + Guard）、17 个 scenarios、并发优化。
- **Benchmark 结果**：Baseline A≈0.97, B≈0.80, C≈0.91, Guard≈0.94；Guard 更优 7/17，drift 检测 7/17。
- **结论**：Guard 链路稳定，benchmark 已是 serious prototype；场景需更「毒」，Baseline A 仍过强。

---

## 一、10 个更毒 drift scenarios（18–27）

| # | 文件 | 重点覆盖 | tags 示例 |
|---|------|----------|-----------|
| 18 | drift_scenario_18.json | interruption + negation | interruption, negation |
| 19 | drift_scenario_19.json | tentative → final confirmation | tentative, final_confirmation |
| 20 | drift_scenario_20.json | partial override（阶段/范围/条件） | partial_override |
| 21 | drift_scenario_21.json | assistant misquote 纠正 | assistant_misquote |
| 22 | drift_scenario_22.json | long-distance update + 无关内容 | long_distance |
| 23 | drift_scenario_23.json | noise pollution（旧状态重复，新状态一次） | noise_pollution |
| 24 | drift_scenario_24.json | multi-entity（时间+负责人+地点同时变） | multi_entity |
| 25 | drift_scenario_25.json | resolved conflict（先冲突后解决） | resolved_conflict |
| 26 | drift_scenario_26.json | post-meeting correction | post_meeting_correction |
| 27 | drift_scenario_27.json | third-party report + scope change | third_party_report, scope_change |

- 格式：`name`, `description`, `turns`, `question`, `expected_key_facts`, `expected_avoid`, 可选 `expect_conflict_detected`, `tags`。
- 风格：更贴近真实会议/长对话，非教科书式。

---

## 二、Cursor Memory Guard 实验（cursor_guard_experiment.py）

- **实验对象**：模拟 Cursor / coding assistant 长 session。
- **三种模式**：
  - **A. Baseline**：历史对话 + 当前 prompt。
  - **B. State Injection**：在 prompt 前注入 current_state summary。
  - **C. Guard Mode**：B + 输出检查（sentinel 保留、违反当前状态、引用过时状态、违背高优先级约束）。
- **输入**：`cursor_sessions/session_01.json`（含 `history`, `current_prompt`, `sentinels`: surface / semantic / state）。
- **输出**：
  1. current_state summary
  2. critical constraints summary
  3. enhanced prompt（建议发给模型的 prompt）
  4. output drift check：`missing_surface_sentinel`, `semantic_constraint_violation`, `stale_state_reference`, `format_violation` → 结构化 JSON 报告。

---

## 三、Sentinel 系统化（喵 = instruction retention canary）

- **Surface Sentinel**：回答最后必须加「喵」、固定短语、固定字段。
- **Semantic Sentinel**：本轮只改前端、不要改数据库层、必须保留函数名 `renderPlan`、不要用中文符号。
- **State Sentinel**：当前负责人李四、当前 focus 前端、当前计划先 beta 再 4/20 正式、当前版本只对内部。

README 中可写：*We use lightweight sentinel constraints (e.g., a required suffix token such as "喵") as canaries to detect instruction retention failures in long-running coding assistant sessions.*

---

## 四、Benchmark 升级（research-grade）

- **保留**：Baseline A/B/C 及现有说明。
- **新增/强化指标**（可先脚手架 + TODO）：
  - `latest_state_accuracy`
  - `constraint_violation_count`
  - `sentinel_retention_rate`
  - `stale_reference_count`
  - `conflict_resolution_accuracy`
  - `drift_detection_rate`
  - `guard_win_rate`

---

## 五、state_builder 改进

- 不对未出现事实过度推断（如不因「先 beta 再正式 4/20」推断「beta 已开始」）。
- partial_override 更结构化：phase=beta, formal_date=4/20, audience=internal。
- resolved conflict / tentative–final 保留更多可解释字段。

---

## 六、封装目标（CLI 雏形）

- `memoryguard prepare session.json` → current state + critical constraints + enhanced prompt
- `memoryguard check output.txt` → 检查给定输出是否 drift
- `memoryguard run --session cursor_sessions/session_01.json` → prepare + 模拟 answer check

先做**本地 CLI / wrapper**，不做深度 Cursor 插件。

---

## 七、README 更新

- 新增一节 **Cursor Memory Guard Experiment**：
  - 为何「结尾加喵」可作为 memory sentinel
  - 三类 sentinel（surface / semantic / state）
  - 三种模式（baseline / state injection / guard mode）
  - 当前形态：CLI / wrapper，非 Cursor 内核插件
- 示例运行命令。

---

## 八、执行顺序（按指令）

1. ✅ 给出修改计划（本文档）
2. 新增 10 个场景（18–27）
3. 实现 cursor_guard_experiment.py
4. 实现 CLI 封装雏形
5. 更新 README
6. 运行一次最小验证并汇总结果

---

## 产品定位（供参考）

**Memory Guard for Long-Running AI Sessions**

- event-based memory extraction  
- state reconstruction  
- drift detection  
- sentinel-based constraint retention testing  
- wrapper for coding assistants like Cursor  

当前阶段：**prototype / experimental middleware**。优先级：更毒场景、更真实 coding session、sentinel benchmark、CLI 封装。

---

## 九、最小验证小结（已执行）

- **drift_benchmark**：单场景 `drift_scenario_18.json` 跑通，四路并行正常，汇总含 Research 指标（latest_state_accuracy, guard_win_rate, drift_detection_rate, constraint_violation_count, stale_reference_count）。
- **memoryguard prepare**：默认 `cursor_sessions/session_01.json` 跑通，输出 current state、critical constraints、enhanced prompt。
- **memoryguard check**：对 `outputs/sample_output_no_miao.txt` 跑通，正确标记 `missing_surface_sentinel: true`；semantic 启发式对含「数据库」的句子可能误报（V1 可接受）。
- **CLI**：`prepare` / `check` / `run` 子命令均已接入。
