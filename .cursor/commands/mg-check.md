## /mg-check — 对最新输出做 Memory Guard drift 检查

你现在是 Memory Guard 的「输出体检官」，目标是在 **当前项目** 里，对我刚生成的一份 Cursor 输出做 drift 检查，重点看：

- 有没有违反 hard constraints（例如「不要动数据库」「不要改后端」「回答结尾加喵」）；
- 有没有把旧负责人 / 旧 deadline / 旧状态又写回来；
- 有没有乱改函数名、乱碰数据库/后端。

### 0. 确认使用哪份状态 & 哪个输出

1. 默认 Session（状态文件）路径：`outputs/imported_state.json`。  
   - 如果不存在，请直接提醒我先跑 `/mg-import`，不要自行假设。
2. 询问我：本次要检查的输出文件路径 `<output_file>` 是什么？  
   - 例如：`outputs/cursor_reply_2025-03-08.txt`，或我刚刚保存的某个回答文件。

### 1. 调用 `memoryguard.py check`

拿到 `<output_file>` 后，在项目根目录执行：

```bash
cd d:\Myfile\memoryos
py -3 memoryguard.py check "<output_file>" --session outputs\imported_state.json
```

注意：
- 如果命令报「输出文件不存在」之类的错误，请先确认路径是否写错，再尝试一次；
- 如果是编码或 Python 环境错误，请把错误信息和你的分析一起告诉我，而不是静默失败。

### 2. 解读 drift 报告（重点提示 hard constraints）

`check` 命令会输出一段 JSON 报告。请帮我做两层总结：

1. **结构化摘要**（简要 bullet）：
   - 是否检测到明显的 drift；
   - drift 集中在哪些方面（负责人、时间、地点、偏好、约束违反等）。
2. **重点标出 hard constraints 是否被违反**：
   - 如果输出违反了类似「不要动数据库」「不要改后端」「回答结尾加喵」这类 hard constraints，请显眼地提醒我；
   - 如果只是 soft constraints（偏好/建议）没完全遵守，可以作为黄色提醒，而不是红色警告。

你可以参考 `imported_state.json` / `import_summary.md` 里的约束内容和之前 `/mg-prepare` 的 Hard/Soft 划分来解释 drift。

### 3. 给出下一步建议

根据 drift 检查结果，用 1～2 句给出建议，例如：

- 「建议你重试一次回答，并在提示里强调 X/Y 这两个 hard constraints」；
- 或「这次回答在 hard constraints 上是安全的，只是 soft constraints（偏好顺序）没有完全按你说的来」。

不要自动改代码或自动重试，只给出**清晰且可执行的建议**，把决策权留给我。

