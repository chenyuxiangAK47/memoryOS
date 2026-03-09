# Memory Guard — 给朋友测试的说明

一个小工具，专门检查 Cursor 这类 AI 在长对话里会不会忘记要求、引用旧状态、或者把约束搞丢。  
你可以拿一个真实的长 session 试一下，它会先帮你整理「当前有效状态」，再检查输出有没有 drift。

---

## 1. 你需要什么

- Python 3.10+
- OpenAI API Key（测试期几美元即可）
- 一个 Cursor 长 session（20+ 轮修改需求那种）

---

## 2. 安装

```bash
# 克隆/下载项目后
cd memoryos
pip install -r requirements-cli.txt   # 或 requirements.txt

# 配置 API Key：复制 .env.example 为 .env，填入 OPENAI_API_KEY
# Windows: copy .env.example .env
# Linux/Mac: cp .env.example .env
```

---

## 3. 2 分钟上手（用官方 demo）

```bash
# 1. prepare：输出 current state + constraints + enhanced prompt
py -3 memoryguard.py prepare

# 2. 把输出的 Enhanced prompt 复制，贴给 Cursor，让它继续回答

# 3. 把 Cursor 的输出保存到 outputs/my_output.txt

# 4. check：检查输出是否 drift
py -3 memoryguard.py check outputs/my_output.txt
```

官方 demo 用的 session 是 `cursor_sessions/session_real_20plus.json`（28 轮待办列表、负责人变更、约束「只改前端」「不动数据库」「保留 getTodoList」「回答加喵」）。

---

## 4. 建议测试的 4 类问题

### 1. 长对话后忘要求

- 回答结尾加「喵」
- 不要改数据库
- 保留某个函数名

### 2. 状态更新后还引用旧信息

- 负责人从张三改成李四
- deadline 改了
- focus 改了

### 3. 需求变多以后开始乱

- 一开始只改前端
- 后面开始动后端
- 中途混进别的任务

### 4. 时间相关 drift

- 明天 / 后天
- 周五前
- 月底前

---

## 5. 需要你的反馈（最重要）

### 1. 它有没有抓到你真的觉得 Cursor 漂了的地方？

有的话，大概在哪些轮、什么类型的 drift？

### 2. 有没有很多误报，让人烦？

比如明明没违反约束，却被判成 drift。

### 3. prepare + check 这个 workflow 值不值得多一步操作？

你觉得这个流程顺不顺？有没有想改进的地方？

---

**只要你说一句：「这个虽然麻烦一点，但确实能看出 Cursor 忘了什么」—— 这个工具就有价值。**

---

## 6. 命令速查

| 命令 | 作用 |
|------|------|
| `py -3 memoryguard.py prepare [session.json]` | 输出 current state + constraints + enhanced prompt |
| `py -3 memoryguard.py check <output.txt> [--session session.json]` | 检查模型输出是否 drift |
| `py -3 memoryguard.py run [--session ...] [--output output.txt]` | prepare + 可选 check |
| `py -3 memoryguard.py benchmark [--all] [scenario.json]` | 跑 Memory Drift Benchmark |
