# 自测记录

## Case: myoutputs.txt

- **Result:** 初版为 False positive（check 误报），修规则后为 **ok**
- **Why:**
  - Output explicitly says "未动后端和数据库"
  - getTodoList signature preserved（签名未改）
  - sentinel "喵" retained
  - no stale state reference
- **Issue:** semantic checker 原先只要出现「数据库」就报 violation；函数名规则曾因「签名」一词误报
- **Fix:** 已加 CONSTRAINT_RULES（safe_patterns / violation_patterns）、negation 附近检测、violation vs warning 分级、函数名仅判明确改名
- **修后 check 结果:** `final_status: "ok"`, `semantic_constraint_violations: []`

## Case: real_session_output_ok.txt

- **Result:** ok（无 violation）
- 含「未动后端和数据库」、有喵、保留 getTodoList → 不误报

## Case: real_session_output_drift.txt

- **Result:** possible_memory_drift（正确检出）
- missing_surface_sentinel、modified_database_layer、changed_required_function_name、used old owner
