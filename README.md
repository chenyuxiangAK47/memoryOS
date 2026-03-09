# AI Memory Guard Demo（v0.2）

**发现会议/聊天中的状态变化、冲突与被覆盖的旧结论，减少 AI 记忆漂移。**

Detect updates, conflicts, and stale conclusions in meeting or chat memory.

---

## Quickstart（2 分钟上手）

给 Cursor 长 session 做 memory drift 检测：

```bash
# 1. 安装
pip install -r requirements-cli.txt
# 复制 .env.example 为 .env，填入 OPENAI_API_KEY

# 2. prepare：输出 current state + constraints + enhanced prompt
py -3 memoryguard.py prepare

# 3. 把输出的 Enhanced prompt 贴给 Cursor，让它继续回答

# 4. 把 Cursor 输出存到 outputs/my_output.txt

# 5. check：检查输出是否 drift
py -3 memoryguard.py check outputs/my_output.txt
```

官方 demo 用 `cursor_sessions/session_real_20plus.json`（28 轮待办、负责人变更、约束：只改前端、不动数据库、保留 getTodoList、回答加喵）。  
给朋友测试的详细说明见 **`TEST_WITH_FRIENDS.md`**。

### 导入旧聊天（import_history）

若**之前没用 MemoryGuard**，可以把一段旧 Cursor/聊天记录导入，自动抽出「当前有效状态」和「关键约束」，再接 prepare/check：

```bash
# 导入旧聊天（支持 .txt / .md / .json session）
py -3 memoryguard.py import_history my_old_chat.txt
# 大文件（如几万行）：只取最后 N 轮，避免 token 超限
py -3 memoryguard.py import_history 测试的markdown/测试用的markdown.md --tail 20
# 默认输出 outputs/imported_state.json、outputs/import_summary.md

# 基于导入状态做 prepare
py -3 memoryguard.py prepare outputs/imported_state.json

# 检查后续输出
py -3 memoryguard.py check outputs/new_output.txt --session outputs/imported_state.json
```

---

## 产品定位

- **名字**：AI Memory Guard  
- **副标题**：帮 AI 识别旧结论、状态更新和记忆冲突，减少记忆漂移  
- **不是**：通用会议总结工具  
- **是**：先提取事件 → 检测更新/冲突 → 输出「当前有效状态」+ 更新列表 + 总结 + 溯源  

## 当前能做什么（v0.2）

- 上传会议记录（.txt / .md / .docx）→ 提取结构化事件
- **运行 Memory Guard**：检测 **update**（后续覆盖前序）与 **conflict**（互相矛盾需人工确认）
- **输出三块**：  
  ① **当前有效状态**（AI 应采用的当前记忆）  
  ② **检测到的更新/冲突**（产品化展示：主题、旧状态、新状态、判定、建议采用、来源）  
  ③ **最终总结**（核心决策、风险、待办）+ 事件溯源
- Guard 结果带 **entity_key**（如 project.launch_plan, feature.face_verification），便于后续接 event log / DB
- 事件保存到 `outputs/events.json`（不接数据库）
- **Memory Guard CLI**：`memoryguard analyze meeting.txt` 一键出报告（含当前有效状态、更新/冲突、总结）
- **state_builder.py**：从 events + Guard findings 构建 state_snapshot / current_state，供「只喂当前状态」推理
- **Memory Drift Benchmark**：对比 **Baseline A（全历史）**、**Baseline B（最近 N 轮）**、**Baseline C（先摘要再答）**、**Guard** 四条路径，算 state accuracy、drift 检测

## 项目结构

```
memoryos/
├── app.py           # Streamlit：上传 → 事件 → Guard → ①当前有效状态 ②更新/冲突 ③总结+溯源
├── demo_mini.py     # 命令行：读文件 → 提取 → 总结 → 保存 events.json
├── extractor.py     # 结构化事件提取
├── memory_guard.py  # 冲突/更新检测（防记忆偏移）
├── summarizer.py    # 带溯源引用的总结
├── schemas.py       # 事件 schema
├── utils.py         # 读文件、分块
├── memoryguard.py   # CLI: memoryguard analyze <file>
├── state_builder.py # events+findings → state_snapshot（供 benchmark / 只喂 state 推理）
├── drift_benchmark.py   # Memory Drift Benchmark：baseline vs Guard
├── scenarios/          # 多轮状态变化场景（drift_scenario_01/02.json）
├── sample_data/meeting.txt
├── outputs/events.json
└── .env
```

---

## MVP 范围（第一版）

1. **上传文本**：支持 txt / markdown（后续可加 docx）
2. **文本切分**：LangChain 拆成 ~200 token 的 chunk
3. **事件提取**：GPT 提取 `event_type, person, content, importance`，只保留 importance ≥ 3
4. **总结**：按事件生成「核心决策 / 风险 / 待办」，并支持**查看来源**

不做：多用户、权限、私有部署、API 平台。

---

## 系统结构

```
用户 → Web UI (Streamlit) → Memory Pipeline → 数据库
```

Pipeline：

```
上传文本 → Text Splitter → Event Extraction (GPT) → Event Log (Postgres)
                                                          ↓
                                    Query + Summarization ← Embedding (pgvector)
```

---

## 需要的资源

| 资源 | 说明 | 大致成本 |
|------|------|----------|
| **OpenAI API Key** | 用于 GPT 事件提取 + 总结 + Embedding | 测试期几美元 |
| **Python 3.10+** | 本地运行 | 免费 |
| **PostgreSQL + pgvector** | 本地 Docker 或云数据库 | 本地免费 / 云约 $5/月 |
| **VPS（可选）** | 要给别人用时再买 | 约 $5/月 |

---

## 7 天开发计划

| 天数 | 任务 |
|------|------|
| Day 1 | 搭环境：Python、LangChain、OpenAI、Postgres+pgvector |
| Day 2 | 文本分块：RecursiveCharacterTextSplitter，测 10 万字 |
| Day 3 | 事件提取：Prompt 设计，输出结构化 JSON，筛选 importance≥3 |
| Day 4 | 事件表建表 + 只追加写入 |
| Day 5 | Embedding 写入 pgvector + 按时间/人物/类型检索 |
| Day 6 | 总结：检索 → 拼 prompt → GPT 生成 + 溯源 |
| Day 7 | Streamlit 界面：上传 → 处理 → 总结 → 查看来源 |

---

## Memory Drift Benchmark（实验验证）

目标：验证 **Memory Guard 是否减少 AI 的 memory drift**。

- **对比**：Baseline（整段对话历史 + 问题 → LLM）vs Guard 路径（仅「当前有效状态」+ 问题 → LLM）
- **场景**：`scenarios/drift_*.json` 共 27 个（01–12 基础与抗漂移，13–17 真实风格，18–27 更毒会议级：打断、否定、暂定确认、助手误复述、长距离、噪声、多实体、冲突解决、会后更正、第三方转述与范围变化）；`scenarios/scenario_taxonomy.md` 为 14 类会议失真模式与标签说明；`scenarios/README_SCENARIO_FORMAT.md` + `_template_drift_scenario.json` 为写新场景用的模板
- **指标**：每个 scenario 有 `expected_key_facts`（正确答案应包含）和 `expected_avoid`（旧结论不应出现）；算 Baseline 得分、Guard 得分、Guard 更优次数、drift 检测次数
- **用法**：`py -3 drift_benchmark.py`（单场景）或 `py -3 drift_benchmark.py --all`（全部场景）

改进方向：增加更多 scenario（100 轮、更多实体）、state_builder 聚合多轮更新以保留「beta + 正式 4/20」等完整状态，即可做成 paper 级 Memory Drift Benchmark。下一阶段目标与执行顺序见 **`PLAN_NEXT_PHASE.md`**。

**抗漂移测试（drift_scenario_03～07）**  
新增 5 个「Baseline 容易飘」的场景，用于证明「Guard 比全历史更稳」：
- **03 噪声污染**：旧状态 4 月 10 日出现多次，最新 4 月 20 日只出现一次；目标看 Baseline 是否被频次带偏。
- **04 长距离更新**：用户住新加坡在开头，搬到东京在很后面，中间大量无关对话；目标看 Baseline 是否仍引用旧地址。
- **05 多步演化**：4 月 10 日 → 4 月 20 日 → 先 beta 再正式 4 月 20 日；问完整计划含阶段；目标看是否丢 beta 或混回 4 月 10 日。
- **06 噪声+长距离**：负责人张三在早期，中间无关对话，后期改为李四；目标看 Baseline 是否仍答张三。
- **07 多实体更新**：上线时间与负责人在不同轮次更新；目标看是否只记得一个忘另一个。

若当前模型下 Baseline 仍全 1.0，可视为模型较强；后续可用更小 context、更弱模型或更长对话再测，观察 Guard 更优次数与 drift 检测次数。

**Baseline B/C**：`drift_benchmark.py` 支持 **Baseline B**（只取最近 `recent_turns` 轮，模拟上下文裁剪）和 **Baseline C**（先对对话做摘要再基于摘要回答，模拟总结丢信息）。场景 JSON 可设 `recent_turns`（默认 6）以控制 B 的窗口。目标：在更毒场景下出现 A/B/C 掉分、Guard 仍稳，从而证明 Guard 有用。

**已做的优化（v0.2.1）**  
- **state_builder**：同一 entity_key 的多个 update 按 event_id 排序，输出 `【演变】s1 → s2 → s3 【当前】s3`，支持 sequence state。  
- **extractor**：显式抽取实体类型 `entity: location | schedule | owner | preference | status`，提高 Scenario 02（地点矛盾）的 recall。  
- **Guard prompt**：要求同一主题多轮变化时分别输出多条 update；事件列表传入 Guard 路径的 LLM prompt 供参考。  
- **Benchmark**：Scenario 02 Guard 得分已可到 1.0；Scenario 01 已通过「对话写直白 + 多步 update」优化，Guard 可稳定 1.0；benchmark 输出含「Guard 看到的当前状态」与「抽取到的事件」便于可视化与迭代。

---

## Cursor Memory Guard Experiment

本项目面向**长对话 / 长 session**（如 Cursor 编码助手）的 memory drift，提供实验性 **Memory Guard 伴生工具**（本地 CLI / wrapper），**不是** Cursor 内核插件。

### 为什么「结尾加喵」可以作为 memory sentinel

在长对话中若要求「回答结尾必须加喵」，当上下文变长时模型有时会忘记该约束。这类轻量级约束可作为 **instruction retention canary**（指令保留探针）：

> We use lightweight sentinel constraints (e.g., a required suffix token such as "喵") as canaries to detect instruction retention failures in long-running coding assistant sessions.

### 三类 Sentinel

| 类型 | 说明 | 示例 |
|------|------|------|
| **Surface** | 表层格式/固定词 | 回答最后必须加「喵」、必须包含某短语、固定字段 |
| **Semantic** | 语义约束 | 本轮只改前端不改后端、不要修改数据库层、保留函数名 `renderPlan` |
| **State** | 当前状态事实 | 当前负责人是李四、当前 focus 是前端页面、当前计划先 beta 再 4/20 正式 |

### 三种模式

- **Baseline**：直接用历史对话 + 当前 prompt 发给模型。
- **State Injection**：在 prompt 前注入 **current_state summary** 与 **critical constraints**。
- **Guard Mode**：State Injection + 对模型输出做 **drift check**（sentinel 是否保留、是否违反当前状态、是否引用过时状态）。

### 当前封装形态

- **CLI**：`memoryguard prepare` / `memoryguard check` / `memoryguard run`（见下方示例）。
- **Session 格式**：`cursor_sessions/session_01.json`（含 `history`、`current_prompt`、`sentinels.surface/semantic/state`）。
- **实验脚本**：`cursor_guard_experiment.py` 可单独运行，输出 current state、constraints、enhanced prompt 及可选的 output drift 报告。

### 示例运行命令

```powershell
# 输出当前状态 + 约束 + 增强 prompt（默认 session_01.json）
py -3 memoryguard.py prepare
py -3 memoryguard.py prepare cursor_sessions/session_01.json

# 检查某段模型输出是否 drift
py -3 memoryguard.py check output.txt
py -3 memoryguard.py check output.txt --session cursor_sessions/session_01.json

# 一键 prepare，若有 --output 则做 drift check
py -3 memoryguard.py run --session cursor_sessions/session_01.json
py -3 memoryguard.py run --session cursor_sessions/session_01.json --output output.txt

# 直接跑实验脚本（输出 state / constraints / enhanced prompt）
py -3 cursor_guard_experiment.py
py -3 cursor_guard_experiment.py cursor_sessions/session_01.json guard
```

---

## 最小测试（不接数据库）

```powershell
# 1. 配置 .env 中的 OPENAI_API_KEY
# 2. 测试 API（Python 3）
py -3 test_openai.py

# 3. 命令行版：读文件 → 事件提取 → 总结 → 保存 events.json
py -3 demo_mini.py
py -3 demo_mini.py 你的会议记录.txt

# 4. 本地页面（Streamlit）
py -3 -m streamlit run app.py

# 5. Memory Guard CLI（事件 + 冲突/更新检测 + 总结）
py -3 memoryguard.py analyze sample_data/meeting.txt

# 6. Memory Drift Benchmark（验证 Guard 是否减少 memory drift）
py -3 drift_benchmark.py                    # 默认跑 scenarios/drift_scenario_01.json
py -3 drift_benchmark.py --all             # 跑全部 scenarios/drift_*.json（含 18–27）
py -3 drift_benchmark.py scenarios/drift_scenario_02.json

# 7. Cursor Memory Guard（prepare / check / run）
py -3 memoryguard.py prepare
py -3 memoryguard.py check output.txt
py -3 memoryguard.py run --session cursor_sessions/session_01.json
py -3 cursor_guard_experiment.py

# Windows 下中文正常显示可设：
$env:PYTHONIOENCODING='utf-8'; py -3 demo_mini.py
```

---

## 本地运行（Streamlit 全功能）

**不连数据库也能先跑通**：只上传 → 分块 → 事件提取 → 总结 → 溯源，事件在当次会话内保存在内存；要持久化再配 Postgres。

```bash
# 1. 虚拟环境（推荐）
python -m venv .venv
.venv\Scripts\activate   # Windows

# 2. 安装依赖
pip install -r requirements.txt

# 3. 配置环境变量（复制 .env.example 为 .env，填 OPENAI_API_KEY）
# 4. 启动 Postgres+pgvector（见 docker-compose.yml 或本地安装，可选）

# 5. 跑 Streamlit
streamlit run app.py
```

---

## 数据库（最小）

一张表 `events`：

- `id`, `timestamp`, `person`, `event_type`, `content`, `importance`, `embedding`（向量）
- 只追加，不修改，便于溯源。

详见 `schema.sql`。
