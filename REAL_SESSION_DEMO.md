# 真实 Session 演示（20+ 轮）

用 **20+ 轮需求变更** 的长 session 跑 `memoryguard prepare` 和 `memoryguard check`，感受 **喵 / constraint / state drift**。

---

## Session 文件

- **`cursor_sessions/session_real_20plus.json`**  
  - 28 轮对话：待办列表前端、负责人从张三→李四→王五、截止从下周五→下下周三→月底前、约束：只前端、不动数据库、保留 getTodoList、回答加喵。  
  - 当前请求：给待办加「完成」勾选，样式变灰+删除线，不改 getTodoList 签名、不动后端和数据库。

---

## 运行

```bash
# 输出当前状态 + 约束 + 增强 prompt
py -3 memoryguard.py prepare cursor_sessions/session_real_20plus.json

# 检查「合规」输出
py -3 memoryguard.py check outputs/real_session_output_ok.txt --session cursor_sessions/session_real_20plus.json

# 检查「漂移」输出
py -3 memoryguard.py check outputs/real_session_output_drift.txt --session cursor_sessions/session_real_20plus.json
```

---

## Prepare 结果摘要

- **Current effective state:** 负责人临时王五；截止月底前。  
- **Critical constraints:** 回答最后必须加喵；不要动数据库；保留 getTodoList；不要改后端；当前负责人王五；focus 首页待办列表；截止月底前。  
- **Enhanced prompt** 已包含上述 state + constraints + 历史 + 当前请求。

---

## Check 结果

| 输出文件 | 内容特点 | 检查结果 |
|----------|----------|----------|
| **real_session_output_ok.txt** | 有「喵」、未改 getTodoList 签名、写「未动后端和数据库」、负责人王五 | `missing_surface_sentinel: false`；因文中出现「数据库」被启发式判为 semantic 违反（误报）。 |
| **real_session_output_drift.txt** | 无「喵」、改成 getTodoListWithDone、写「数据库那边也加了一个」、提到张三 | `missing_surface_sentinel: true`；`semantic_constraint_violations` 含 modified database；`final_status: possible_memory_drift`。 |

结论：**喵** 作为 surface sentinel 能稳定检出「忘记结尾加喵」；**constraint** 和 **state** 的自动检查目前是启发式（如出现「数据库」即报违反），后续可改为更细的规则或模型判读。

---

在 Cursor 里真实玩 20+ 轮修改需求后，把最后一段模型输出存成文件，用 `memoryguard check` 跑一遍即可复现上述流程。
