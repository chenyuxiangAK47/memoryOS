# MemoryGuard v2-alpha — Live Guard Demo

本文档固定 v2-alpha 的演示步骤与预期输出，便于 README、录屏、发帖或给他人复现。

---

## 1. Clean 场景（合规回复）

**命令（PowerShell 下直接复制）：**

```powershell
cd D:\Myfile\memoryos

py -3 memoryguard.py guard-chat --state outputs/imported_state_demo.json --scenario clean --prompt "Optimize todo loading"
```

**预期输出：**

- 终端打印：
  ```
  No drift detected.
  The reply stays consistent with the current state and constraints.

  Saved: D:\Myfile\memoryos\outputs\live_guard_result.json
  Saved: D:\Myfile\memoryos\outputs\live_guard_result.md
  ```
- 生成文件：
  - `outputs/live_guard_result.json`：含 `enhanced_prompt`、`ai_response`、`guard_result`（`final_status: "ok"`）、`readable_summary`
  - `outputs/live_guard_result.md`：即 readable summary 的纯文本

---

## 2. Drift 场景（违规回复）

**命令（PowerShell 下直接复制）：**

```powershell
cd D:\Myfile\memoryos

py -3 memoryguard.py guard-chat --state outputs/imported_state_demo.json --scenario drift --prompt "Optimize todo loading (root-cause)"
```

**预期输出：**

- 终端打印：
  ```
  Drift detected.
  The reply may violate earlier constraints or current state assumptions.

  Key reasons:
  - The reply suggested modifying the database layer or schema.
  - The reply suggested modifying backend code or APIs.
  - The reply suggested renaming or changing a required function name.

  Saved: D:\Myfile\memoryos\outputs\live_guard_result.json
  Saved: D:\Myfile\memoryos\outputs\live_guard_result.md
  ```
- 生成文件：
  - `outputs/live_guard_result.json` 中 `guard_result.final_status` 为 `"possible_memory_drift"`，`guard_result.semantic_constraint_violations` 包含上述三项。
  - `outputs/live_guard_result.md` 内容与终端打印的 readable summary 一致。

---

## 3. 结果文件结构（参考）

`live_guard_result.json` 的固定结构：

```json
{
  "state_path": "outputs/imported_state_demo.json",
  "user_prompt": "...",
  "enhanced_prompt": "...",
  "ai_response": "...",
  "guard_result": {
    "final_status": "ok" | "possible_memory_drift",
    "semantic_constraint_violations": [],
    ...
  },
  "readable_summary": "..."
}
```

- **clean**：`final_status` 为 `"ok"`，violations 为空。
- **drift**：`final_status` 为 `"possible_memory_drift"`，violations 至少包含 `modified_database_layer`、`modified_backend`、`changed_required_function_name`（视 mock 文案而定）。

---

## 4. GUI Tab 5 怎么看

1. 启动 Gradio：  
   `py -3 app.py`  
   浏览器打开给出的本地地址。

2. 切换到 **「5. Live Guard」** Tab。

3. 输入区：
   - **State file**：默认 `outputs/imported_state_demo.json`（可改）
   - **Mock scenario**：选 `clean` 或 `drift`
   - **User prompt**：例如 `Optimize todo loading` 或 `Optimize todo loading (root-cause)`

4. 点击 **「Run Live Guard (mock)」**。

5. 输出区会依次显示：
   - **Enhanced prompt**：注入约束后的完整 prompt
   - **AI response (mock)**：当前为 mock 模型返回的文本
   - **Guard result (JSON)**：与 CLI 的 `guard_result` 一致
   - **Readable Summary**：与终端 / `live_guard_result.md` 一致的人话说明

- **clean**：Readable Summary 为 “No drift detected...”
- **drift**：Readable Summary 为 “Drift detected...” + Key reasons 列表

---

## 一句话总结

- **Clean 命令** → No drift detected，结果写入 `live_guard_result.json` / `.md`。
- **Drift 命令** → Drift detected + key reasons，同上。
- **GUI Tab 5** → 同一套逻辑，用界面选 scenario 和 prompt，看四块输出。

先收口，再接真模型。

---

## 5. 使用真实模型（OpenAI）

需要设置环境变量 `OPENAI_API_KEY`，然后可使用：

```powershell
py -3 memoryguard.py guard-chat --state outputs/imported_state_demo.json --model openai --provider-model gpt-4o-mini --prompt "Optimize todo loading"
```

- `--model openai` 使用 OpenAI 真实调用；不写时默认为 `mock`。
- `--provider-model` 可选，默认 `gpt-4o-mini`。
- 输出格式与 mock 相同（`live_guard_result.json` / `.md`）。

GUI Tab 5 中 Provider 选 `openai`，在「Provider model」中填写模型名即可。
