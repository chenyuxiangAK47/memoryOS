## /mg-import — 导入旧聊天为 Memory Guard 状态

你现在是 Memory Guard 的 CLI 操作员，帮我在 **当前项目（d:\\Myfile\\memoryos）** 里，把一段旧聊天导入成 `imported_state.json`，供后续 `/mg-prepare` 和 `/mg-check` 使用。

请严格按下面步骤执行，不要跳过：

### 1. 确认要导入的历史文件

1. 先问我：这次要导入哪一段历史？支持：
   - `.txt` / `.md`：例如我从 Cursor 导出的 Markdown，或手动复制粘贴保存的聊天日志；
   - `.json`：`session.json` 这种已有的 Memory Guard session。
2. 如果我没有指定路径，可以**建议**我从这些里选一个或告诉你完整路径：
   - `测试的markdown/测试用的markdown.md`
   - 或我项目里其它聊天导出文件。

不要自己瞎猜路径，一定用我确认的那个。

### 2. 调用 `import_history`（分块 + 规则优先）

拿到历史文件路径 `<history_file>` 后，在项目根目录执行：

```bash
cd d:\Myfile\memoryos
py -3 memoryguard.py import_history "<history_file>" --chunked --no-llm
```

说明：
- `--chunked`：按行分块处理大文件，避免一次性塞进模型；
- `--no-llm`：先只用规则抽取状态和约束，成本最低；如果我想要更丰富的状态，可以再跑一遍不带 `--no-llm` 的版本。

如果命令报错，请：
1. 读完错误信息；
2. 判断是路径问题、编码问题还是 Python 环境问题；
3. 尝试修正后**再重试一次**；只有明确无法修时，再把错误和你的判断一起告诉我。

### 3. 向我汇报导入结果

命令成功后，请检查并简要汇报：

- 控制台输出中的这些统计字段：
  - `lines_processed`
  - `chunks`
  - `events_extracted`
  - `state_updates`
  - `constraints`
  - `conflicts`
- 是否成功生成了：
  - `outputs/imported_state.json`
  - `outputs/import_summary.md`
  - `outputs/event_log.json`

然后用**一句话**总结这次导入的“侧重点”，例如：

- 「这次导入主要识别到的是出生点相关状态和约束」；
- 或「这次导入主要抽到的是约束，状态更新很少」。

最后提醒我：可以用 `/mg-prepare` 在 Cursor 里生成 Enhanced prompt，用 `/mg-check` 对新的回答做 drift 检查。

