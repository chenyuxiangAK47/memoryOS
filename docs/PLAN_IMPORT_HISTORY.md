# import_history MVP — 实现计划

## 目标

**Retroactive memory import / backfill**：用户以前和 Cursor/ChatGPT 聊了很多轮，那些历史没经过 MemoryGuard。现在把这些旧聊天「补建」为当前有效状态和关键约束，让后续输出继续受 Guard 约束。目标不是做更复杂的系统，而是解决这个实际问题。

用户把一段**旧聊天记录**（未用过 MemoryGuard）导入，系统自动提取「当前有效状态」和「关键约束」，输出可供 prepare/check 使用的状态文件。

## 步骤

1. **import_history.py**
   - 读入 .txt / .md / .json（session 格式）
   - 解析对话角色（用户/助手、User/Assistant、Round N 用户/助手），转成统一 turns
   - 复用：turns_to_text → extract_events → detect_conflicts_and_updates → build_state_snapshot
   - 从 snapshot 生成 current_effective_state（key/value 列表）
   - 从 findings 生成 state_updates（from/to）、conflicts
   - 从对话文本启发式抽取 critical_constraints（不要/保留/只改/喵 等）
   - 输出 imported_state.json + import_summary.md

2. **CLI**
   - `memoryguard.py import_history <file> [--out path] [--summary path]`
   - 默认 --out outputs/imported_state.json, --summary outputs/import_summary.md

3. **prepare/check 兼容**
   - 读取 session 时若 `import_mode == "history_import"`，则用 current_effective_state 拼 current_state_summary，用 critical_constraints 拼 sentinels（全部放入 semantic，含喵的入 surface）
   - prepare 无 history 时仅输出 state + constraints；check 照常

4. **验证**
   - 用 session_real_20plus 的 history 导出为 .txt 或直接用 .json 做 import，再 prepare + check 走通

## 不做

向量库、MCP、GUI、插件、多 Agent、自动拒绝输出。
