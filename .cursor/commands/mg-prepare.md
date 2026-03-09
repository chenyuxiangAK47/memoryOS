## /mg-prepare — 基于导入状态生成 Enhanced prompt（含 hard/soft constraints）

你现在是 Memory Guard 的「提示工程助手」，目标是在 **Cursor 当前项目** 里，基于 `imported_state.json` 生成一份可直接复制使用的 Enhanced prompt，并把约束拆成：

- `Hard constraints`：**不能违反** 的要求（例如「不要动数据库」「不要改后端」「回答最后必须加喵」）；
- `Soft constraints`：偏「建议/偏好/优先级」的说明。

### 0. 默认使用哪个状态文件

1. 默认状态文件路径为：`outputs/imported_state.json`。
2. 如果该文件不存在，请直接提醒我先运行 `/mg-import`，不要胡乱假设。

### 1. 获取当前状态与约束

有两种方式，你可以二选一：

1. **优先方案：直接读取 JSON**  
   - 读取 `outputs/imported_state.json`；
   - 使用字段：
     - `current_effective_state`：`[{ "key": ..., "value": ... }]`；
     - `critical_constraints`: `string[]`。
2. 备选方案：调用 CLI 并从输出中提取  
   - 在项目根目录执行：

```bash
cd d:\Myfile\memoryos
py -3 memoryguard.py prepare outputs\imported_state.json
```

   - 从输出的 `--- Current effective state ---` 和约束部分获取内容。

**推荐优先直接读 JSON**，这样可以更稳定地做 hard/soft 拆分。

### 2. 把约束拆成 hard / soft

对 `critical_constraints` 中的每一条，按如下启发式拆分：

- 归为 **Hard constraints** 的典型关键词/模式：
  - 含有：`不要`、`不能`、`不准`、`不得`、`禁止`、`严禁`、`绝对不能`、`不可以`、`别动`、`别改`；
  - 含有：`必须`、`一定要`、`务必`；
  - 明确禁止/限制范围的，如：`不要动数据库`、`不要改数据库`、`不要动后端`、`不要改后端`、`只做前端`、`只改前端`；
  - 含有 `喵` 且是对回答格式的约束，例如「回答最后必须加喵」。
- 其余约束，默认归为 **Soft constraints**。

请去重，并保持原有出现顺序。

### 3. 生成 Enhanced prompt 文本

用下面的结构生成一段可复制的 Enhanced prompt，并在聊天中展示出来（用 Markdown 代码块包住，方便我复制）：

```text
【当前有效状态】请务必遵守以下状态与约束。

Current effective state:
- [key1] value1
- [key2] value2
...

Hard constraints:
<一条一行列出 hard constraints，如无则写 "（无）">

Soft constraints:
<一条一行列出 soft constraints，如无则写 "（无）">

---
（请在此输入当前请求，或粘贴后续问题）

请根据上述「当前有效状态」和「Hard constraints / Soft constraints」回答，尤其不要违反 Hard constraints。
```

其中 `Current effective state` 部分请用 `current_effective_state` 的内容生成，格式类似：

- `- [user.preference] 用户建议 Cursor 按优先级回答侠义骑士不生效的问题。`
- `- [originSystem.location] 当前选定的出生位置为 vlandia。`

### 4. 向我展示摘要 + 可复制块

在本次命令的回复中，请包含：

1. 一个简短摘要：当前识别到多少条状态、多少条 hard / soft constraints；
2. 一段**可直接复制**的 Enhanced prompt（放在 Markdown 代码块里，语言标签可省略）。

不要夹杂多余解释文字到代码块里，保证我复制后可以直接粘贴给 Cursor 作为新的提问。

