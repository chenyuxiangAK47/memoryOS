# History Import Validation — Stage 1

## One‑sentence summary

On a real 40k‑line Cursor conversation log, MemoryGuard successfully reconstructed a usable imported state, improved prompt grounding, and validated the resulting answer as drift‑free.

---

## Scenario 1: 40k‑line Cursor log (OriginSystem / 出生点)

- **Source**: `测试的markdown/测试用的markdown.md` — ~40k lines of a real Cursor conversation about OriginSystem 出生点 / 侠义骑士 / 逃奴修复。
- **Import command**:

```bash
py -3 memoryguard.py import_history "测试的markdown\测试用的markdown.md" --chunked
```

- **Import stats** (chunked pipeline):
  - `lines_processed`: 40442  
  - `chunks`: 21  
  - `events_extracted`: 6  
  - `state_updates`: 0  
  - `constraints`: 3  
  - `conflicts`: 0  

Resulting `outputs/imported_state.json` contained:

- `current_effective_state` ≈ `event.latest = 当前待定位置为 vlandia`  
- `critical_constraints`（3 条，均为软约束）：
  - 「还是只做了加钱加兵但没设置出生点，所以看起来‘没生效’」
  - 建议将 `ApplyPresetOrigin()` 移到 `OnCharacterCreationIsOver`，而 `OnSessionLaunched` 只做菜单注册 / 初始化，不再做出身 Apply。

---

## Workflow

### 1. Import (`/mg-import` + `import_history`)

- 在 Cursor 里通过 `/mg-import` 触发：  
  - 选择历史文件 `测试的markdown/测试用的markdown.md`；  
  - 调用 `memoryguard.py import_history`（分块 + 规则优先 + 可选 LLM）；  
  - 生成：`outputs/imported_state.json`、`outputs/import_summary.md`、`outputs/event_log.json`。

### 2. Prepare (`/mg-prepare` + `prepare`)

- 在 Cursor 中使用 `/mg-prepare` 基于 `outputs/imported_state.json` 生成 Enhanced prompt：
  - **Current effective state**：`[event.latest] 当前待定位置为 vlandia`。
  - **Hard constraints**：本次为空（无明确“不要动 DB / 只改前端 / 喵”类强约束）。
  - **Soft constraints**：3 条关于「只改钱兵」「没设置出生点」「职责拆分（OnCharacterCreationIsOver vs OnSessionLaunched）」的工程建议。
  - Enhanced prompt 将上述 state + hard/soft constraints 统一注入到新的 Cursor 对话首条消息中。

### 3. Answer in Cursor

- 在新对话中粘贴 Enhanced prompt，并追加真实问题（出生点修复方案）。
- Cursor 的回答核心结论：
  - 确认「只在 `OnSessionLaunched` 里做 ApplyPresetOrigin() 很容易导致‘钱和兵改了，但出生点没生效’」。
  - 建议将「真·出生点逻辑」放在 `OnCharacterCreationIsOver` 中调用 `ApplyPresetOrigin()`，`OnSessionLaunched` 仅负责菜单和行为初始化。
  - 示例代码展示如何在 `ApplyPresetOrigin()` 中真正设置 `Culture` / `Settlement` / `Position`，使主角出生在 vlandia，而不只是数值修改。

### 4. Check (`/mg-check` + `check`)

- 将该回答保存为 `outputs/reply_vlandia.txt`，运行：

```bash
py -3 memoryguard.py check outputs\reply_vlandia.txt --session outputs\imported_state.json
```

- Drift 报告：

```json
{
  "sentinel_retained": true,
  "missing_surface_sentinel": false,
  "semantic_constraint_violations": [],
  "semantic_constraint_warnings": [],
  "stale_state_references": [],
  "format_violation": false,
  "final_status": "ok"
}
```

解释：在这份导入状态 + 约束下，这次回答**没有违反任何约束**、**没有引用过期状态**，被判定为 drift‑free。

---

## Evaluation against the 4 questions

1. **能不能把真正关心的约束抽出来？**  
   - 本例历史记录的约束主要是「出生点逻辑的时机和职责拆分」，导入出的 3 条 soft constraints 与工程痛点高度一致。暂时没有硬约束（例如“不动数据库”“只前端”），这与原对话内容匹配。

2. **会不会把旧状态和新状态分清？**  
   - 导入结果只保留了最新的 `event.latest = 当前待定位置为 vlandia`，没有把早期的候选出身当作当前状态；后续回答也始终围绕 vlandia，没有回滚到旧状态。

3. **会不会乱推断？**  
   - state 中没有虚构负责人/截止时间，回答只是在给定状态+约束下扩展出合理的工程落地方式（hook 时机与代码结构），未发明额外业务事实。

4. **导入后的 prepare 有没有明显更有帮助？**  
   - 对比原先「Cursor 听不懂人话」的体验，这次在 Enhanced prompt 中注入「当前待定位置 = vlandia + 出生点职责拆分」后，回答直接命中了「为什么看起来没生效」这一核心问题，并给出贴合上下文的修复方案；随后 `/mg-check` 也确认此回答在当前 imported state 下 drift‑free。

结论：在这份 40k‑line 真实 Cursor 聊天上，`import_history → prepare → check` 这条链路被完整验证为**可用**且**对工程问题有实际增益**，可以作为后续扩展（第二份真实聊天、朋友试用、后期 hooks 自动化）的坚实基础。

---

## Scenario 2: 20+ turn coding session (owner / deadline / constraints)

- **Source**: `cursor_sessions/session_real_20plus.json` — 28‑turn coding session about a small front‑end todo page.  
  - Owner drift: 张三 → 李四 → 临时王五。  
  - Deadline drift: 下周五 → 下下周三 → 月底前。  
  - Constraints: 只前端、不动数据库、保留 `getTodoList`、回答结尾加喵。
- **Import command**:

```bash
py -3 memoryguard.py import_history cursor_sessions\session_real_20plus.json --out outputs\imported_state_session_real_20plus.json --summary outputs\import_summary_session_real_20plus.md
```

- **Import result** (`outputs/imported_state_session_real_20plus.json`):
  - `current_effective_state`：
    - `user.focus = 当前关注点还是首页这个列表，别的先不做。`
    - `user.schedule = 截止时间改为月底前交就行。`
    - `user.owner = 负责人临时换成王五。`
  - `state_updates` 明确从「原负责人/截止未明确」更新到「临时负责人王五 / 截止月底前」。
  - `critical_constraints` 汇总出软硬约束混合列表（只前端、不动数据库、保留 `getTodoList`、回答加喵、当前负责人/截止/focus 等）。

### Prepare on imported state

Running:

```bash
py -3 memoryguard.py prepare outputs\imported_state_session_real_20plus.json
```

produces:

- **Current effective state**:
  - `[user.focus] 当前关注点还是首页这个列表，别的先不做。`
  - `[user.schedule] 截止时间改为月底前交就行。`
  - `[user.owner] 负责人临时换成王五。`
- **Hard constraints**（示例）：
  - 只做前端待办列表（不做后端）
  - 用 React，不要用 Vue
  - 回答最后必须加喵
  - 不要动数据库，我们只做前端 mock 数据
  - 只做前端 + mock，不动数据库
  - 必须保留 `getTodoList` 函数名
  - 不要动数据库 / 不要改后端
- **Soft constraints**：
  - 保留 getTodoList（重复表述）
  - 当前负责人是王五
  - 当前 focus 是首页待办列表
  - 当前截止是月底前

Enhanced prompt 将上述 state + hard/soft constraints 注入到新的 Cursor 提示中。

### Check on a known “good” answer

- 使用已有的合规输出：`outputs/real_session_output_ok.txt`（有喵、未改 `getTodoList`、声明未动数据库和后端）。  
- 运行：

```bash
py -3 memoryguard.py check outputs\real_session_output_ok.txt --session outputs\imported_state_session_real_20plus.json
```

- Drift 报告：

```json
{
  "sentinel_retained": true,
  "missing_surface_sentinel": false,
  "semantic_constraint_violations": [],
  "semantic_constraint_warnings": [],
  "stale_state_references": [],
  "format_violation": false,
  "final_status": "ok"
}
```

解释：在通过 `import_history` 补建出来的状态 + 约束下，这份“好答案”被判定为：

- 保留了喵（surface sentinel 正常）；  
- 未违反「不动数据库」「保留 getTodoList」「不改后端」等 hard constraints；  
- 使用了最新的 owner / deadline / focus 状态（临时负责人王五 / 截止月底前 / focus 首页列表），未引用旧的张三 / 李四 / 下周五 / 下下周三；  
- 综合判定 `final_status: "ok"`，即无明显 drift。

---

Overall, two distinct real‑world conversations (40k‑line engineering log, and 20+‑turn coding session with owner/deadline drift) both validate that `import_history → prepare → check` can reconstruct a usable current state and constraints, improve prompt grounding, and reliably flag—or in these two cases, clear—drift.

