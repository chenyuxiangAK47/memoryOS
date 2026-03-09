# import_history 验证清单

**目标**：retroactive memory import — 把「以前没经过 MemoryGuard 的旧聊天」补建为当前有效状态 + 关键约束，让后续输出继续受 Guard 约束。

---

## 用「气死你」那段旧聊天测什么

### 1. 能不能把你真正关心的约束抽出来

- **看**：`import_summary.md` 里「关键约束」、`imported_state.json` 里 `critical_constraints`。
- **问**：你当时反复强调、希望模型遵守的那几条（例如「只改前端」「别动数据库」「保留某函数名」「回答加喵」），有没有被抽出来？
- **好**：真正在意的约束都出现、且表述清晰。  
- **差**：漏掉你特别在意的，或塞进一堆无关的「约束」。

---

### 2. 会不会把旧状态和新状态分清

- **看**：`import_summary.md` 里「当前有效状态」vs「状态更新」；`imported_state.json` 里 `current_effective_state` 与 `state_updates`。
- **问**：负责人/截止时间/focus 等，最终结论是否对？是否没有把「已经改掉的旧说法」当当前状态？
- **好**：当前状态是最后一次更新后的结果；更新链（张三→李四→王五）清晰。  
- **差**：当前状态里还出现已被后续改掉的旧值，或更新顺序颠倒。

---

### 3. 会不会乱推断

- **看**：当前有效状态和约束里有没有「对话里从没明确说过」的东西。
- **问**：例如「先 beta 再正式 4/20」有没有被推断成「beta 已开始」？「月底前」有没有被自动写成具体日期（在没给时间锚点时）？
- **好**：只写对话里出现或明确更新过的内容，不确定的进 conflicts/待确认。  
- **差**：自己补时间、补阶段、补「已确认」等。

---

### 4. 导入后的 prepare 有没有明显更有帮助

- **操作**：  
  - 先不导入：用「整段旧聊天 + 当前问题」直接问 Cursor（或只看原始长对话）。  
  - 再导入：`import_history` → `prepare outputs/imported_state.json`，用输出的 **Enhanced prompt**（当前状态 + 关键约束 + 你的新问题）去问 Cursor。
- **问**：第二种方式下，模型是否更少「忘记约束、引用旧状态、听不懂人话」？
- **好**：prepare 后的 prompt 让后续回答明显更贴约束、少漂移。  
- **差**：和直接贴长对话差不多，或更乱。

---

## 怎么跑

```bash
# 1. 把「气死你」那段聊天存成 .txt 或 .md（用户/助手 或 **User**/**Cursor** 块格式均可）
# 2. 导入（若文件很大，用 --tail 只取最后 N 轮，避免 token 爆掉）
py -3 memoryguard.py import_history 你的旧聊天.md
# 大文件示例（约 4 万行、几十轮）：只取最后 20 轮
py -3 memoryguard.py import_history 测试的markdown/测试用的markdown.md --tail 20

# 3. 看摘要
# 打开 outputs/import_summary.md

# 4. 用导入状态做 prepare
py -3 memoryguard.py prepare outputs/imported_state.json

# 5. 把 prepare 输出的 Enhanced prompt 贴给 Cursor，问一个后续问题，再 check 输出
py -3 memoryguard.py check outputs/新输出.txt --session outputs/imported_state.json
```

---

## 一句话

**功能目标**：旧聊天 → 补建状态与约束 → 后续继续受 Guard 约束。  
**验证目标**：约束抽得准、新旧状态分清、不乱推断、prepare 明显更有用。
