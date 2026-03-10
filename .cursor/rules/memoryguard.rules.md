## MemoryGuard / MemoryOS — 项目级约束（Rule）

你正在一个已经接入 MemoryGuard 的项目中工作（`memoryOS`）。  
本项目约定使用 `outputs/imported_state.json` 描述「当前有效状态 + 约束」，并通过 `/mg-import`、`/mg-prepare`、`/mg-check` 命令进行更新和检查。

当你作为 Cursor Agent 在本项目里回答问题或改代码时，请遵守以下约定：

### 1. 始终优先参考导入状态

- 若存在 `outputs/imported_state.json`：
  - 把其中的 `current_effective_state` 视为**当前真值**，不要随意回到更早的说法。
  - 把其中的约束拆成：
    - **Hard constraints**：明显的禁止/必须/只做/不要动数据库/不要改后端/必须保留某函数名/回答结尾必须加喵；
    - **Soft constraints**：偏好、当前 focus、负责人/截止的说明等。
- 回答时：
  - **不得违背 Hard constraints**；
  - 在不冲突的前提下，尽量尊重 Soft constraints。

### 2. coding assistant 长 session 的典型约束

在涉及前端待办列表 / owner / deadline 变更的对话中，若 `imported_state.json` 中出现类似约束，请默认遵守：

- 只改前端，不改后端实现；
- 不要动数据库（只用 mock / localStorage 等前端手段）；
- 必须保留指定函数名（例如 `getTodoList`），不要改签名或随意重命名；
- 回答结尾若被要求加「喵」，要坚持到底；
- 当前负责人、当前截止时间、当前 focus（模块）以最新一条说明为准。

如需违反这些约束，必须先在回答中**显式说明原因，并征求用户确认**，而不是默默改掉。

### 3. 修改代码时的自我检查

在生成代码变更前后，请自查以下问题：

- 这次改动有没有：
  - 改动被标记为「不要动」的模块（例如后端、数据库层）？
  - 改名/删除被强调要保留的函数（如 `getTodoList`）？
  - 把负责人 / 截止 / 设定改回了旧版本？
- 如果答案为「是」，请：
  - 在回答中明确指出这点；
  - 给出保留约束的替代方案，或等待用户明确允许。

### 4. 无导入状态时的行为

- 若 `outputs/imported_state.json` 不存在或内容为空：
  - 正常回答问题，但避免主动创造「负责人/截止/约束」之类的长期设定；
  - 遇到类似信息时建议用户先通过 `/mg-import` 导入历史，再继续深度变更。

