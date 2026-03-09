# Drift Scenario JSON 格式说明（给 Cursor / ChatGPT 写「狠毒」场景用）

## 用途

每个 JSON 文件描述一个 **Memory Drift Benchmark** 场景：多轮对话 + 一道问题 + 期望答案要点。  
Benchmark 会跑 **Baseline A（全历史）**、**Baseline B（最近 N 轮）**、**Baseline C（先摘要再答）**、**Guard** 四条路径，并比较得分。

目标：设计「Baseline 容易飘、Guard 相对更稳」的场景，从而证明 Guard 有用。

---

## 字段说明

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `name` | string | 是 | 场景 ID，如 `drift_scenario_08`，文件名建议与之一致 |
| `description` | string | 否 | 中文简述：设计意图、为何 Baseline 容易错 |
| `turns` | array | 是 | 对话轮次，每项 `{"role": "user"\|"assistant", "content": "..."}` |
| `question` | string | 是 | 最后要问的问题（当前状态 / 当前负责人 / 当前计划等） |
| `expected_key_facts` | array | 是 | 正确答案**必须包含**的短语（如 `["4月20日", "李四"]`），缺一个扣分 |
| `expected_avoid` | array | 否 | 正确答案**不应出现**的旧状态（如 `["4月10日", "张三"]`），出现则扣分 |
| `recent_turns` | number | 否 | Baseline B 只用最近几轮，默认 6。长对话时可设 8 或 10，让 B 更容易丢信息 |
| `tags` | array | 否 | 场景类型标签，用于统计。见 `scenario_taxonomy.md`，如 `["interruption", "partial_override"]` |
| `description_en` | string | 否 | 英文简述，便于论文/README |
| `tags` | array of string | 否 | 本场景所属的 case 类型，用于统计与 taxonomy 对齐。见 `scenario_taxonomy.md` |

---

## 设计「狠毒」场景的 4 类思路

1. **高频旧状态污染**  
   旧状态出现 10～20 次，中间夹无关，最后只改一次。例：前 15 轮反复提 4 月 10 日，第 16 轮改成 4 月 20 日，再 5 轮无关，问当前上线时间。`expected_key_facts`: `["4月20日"]`，`expected_avoid`: `["4月10日"]`。

2. **长距离 + 多实体干扰**  
   多个实体（上线时间、负责人、所在地）在不同轮次更新，中间插 15～20 轮无关闲聊，最后问「当前上线时间、负责人、所在地分别是什么」。`expected_key_facts`: `["4月20日", "李四", "东京"]`，按需 `expected_avoid`。

3. **相似表述诱导**  
   旧状态和新状态表述很像，易造成 retrieval drift。例：「4 月 10 日前上线正式版」「4 月 20 日上线 beta 后的正式版」「先 beta，正式版 4 月 20 日」。问题要明确问「当前完整计划」。

4. **多轮修正链**  
   5 次以上连续更新（v1→v2→v3→v4→v5），问「完整方案」。例：v1 4月10日正式 → v2 改4月20日 → v3 先beta再4月20日正式 → v4 beta只对内部 → v5 正式推到4月25日。`expected_key_facts` 要包含最终所有关键点。

---

## 模板（复制后改内容即可）

```json
{
  "name": "drift_scenario_XX",
  "description": "一句话说明为何 Baseline 容易飘、Guard 应更稳",
  "turns": [
    {"role": "user", "content": "用户说的话"},
    {"role": "assistant", "content": "助手回复"},
    {"role": "user", "content": "..."}
  ],
  "question": "最后要问的问题，例如：当前上线时间/负责人/所在地/完整计划是什么？",
  "expected_key_facts": ["必须出现的关键词1", "必须出现的关键词2"],
  "expected_avoid": ["不应出现的旧状态1"],
  "recent_turns": 6,
  "description_en": "Optional English description."
}
```

- `turns` 按时间顺序，最后一轮可以是助手确认，问题在 benchmark 里统一在最后问。  
- 想让 **Baseline B** 更容易丢信息：对话总轮次明显大于 `recent_turns`（如 25 轮对话 + `recent_turns: 6`）。  
- 想让 **Baseline C** 丢信息：关键更新分散在多处，摘要容易漏掉某一处更新。

---

## 文件名约定

- 正式场景：`drift_scenario_01.json` … `drift_scenario_17.json`（可继续往后加）。  
- **Scenario 类型与标签**：见 `scenario_taxonomy.md`，含 14 类真实会议失真模式（update, interruption, tentative, resolved_conflict 等），写新场景时可按 tag 覆盖。  
- 运行全部：`py -3 drift_benchmark.py --all` 会扫描 `scenarios/drift_*.json`（不含 `_template`）。
