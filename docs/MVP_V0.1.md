## 1. 项目做什么

MemoryOS / MemoryGuard 是一个用于 LLM coding sessions 的 **state reconstruction + drift detection 工具**。

它可以从历史对话中重建：
- current state
- constraints

并在后续回答中检测 memory drift。

## 2. 核心流程

整体交互流建议统一为：

- **import_history**：从现有聊天记录 / agent transcript 中导入上下文，构建“事实状态 + 约束”的初始快照。
- **prepare**：基于导入结果，生成“当前有效状态 + Hard/Soft constraints + 强化 prompt”，用于后续 ask / guard。
- **ask**：用户在强化 prompt 下继续 coding 对话，工具在后台跟踪 state / constraints 的演化。
- **check**：对新的回答做 drift guard，对比“最新回答”与“当前有效状态 / 约束”，检测违背约束、遗忘关键 state、逻辑自相矛盾等问题。

在这个流程上，我建议直接开始 Stage 3B：diff guard。

## 3. 为什么现在先做 Stage 3B：diff guard

这一步会让你的系统从：

- 只是“聊天安全工具”（只看对话文本是否违背约束）

变成真正意义上的：

- **coding guard**（不仅看回答内容，还看代码改动是否和约束 / 当前 state 一致）

通过在 `ask → check` 阶段引入 **diff guard（例如 `py -3 memoryguard.py guard-diff`）**，可以在每轮回答后：

- 直接读取当前 `git diff` 中的改动文件；
- 将“代码层面的实际改动”纳入 drift 检测；
- 为后续更强的 rule-checking / policy enforcement 打下基础。

## 4. 平台无关 + Desktop GUI

- **不绑定 Cursor**：历史导入支持 **Cursor / Gemini / ChatGPT / Claude** 等导出的对话格式（块格式如 `**User**` / `**Assistant**` / `**Gemini**` 等），任意平台导出的 .md / .txt / .json 均可导入。
- **MemoryGuard Desktop**：本地小 GUI，无需手打命令行。  
  - 运行：`py -3 memoryguard.py gui` 或 `py -3 memoryguard_gui.py`  
  - 功能：选择历史文件 → Run Import；选择状态文件 → Run Prepare；选择回答文件 → Run Check；结果在右侧输出，可导出并打开输出目录。
