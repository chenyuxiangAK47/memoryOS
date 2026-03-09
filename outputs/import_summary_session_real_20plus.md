# Memory Guard — 导入摘要

**来源文件**: `D:\Myfile\memoryos\cursor_sessions\session_real_20plus.json`

## 当前有效状态

- **user.focus**: 当前关注点还是首页这个列表，别的先不做。
- **user.schedule**: 截止时间改为月底前交就行。
- **user.owner**: 负责人临时换成王五。

## 关键约束

- 好的，只做前端待办列表
- 你先用 React，不要用 Vue
- 回答最后必须加喵
- 不要动数据库，我们只做前端 mock 数据
- 只做前端 + mock，不动数据库
- 有个函数名必须保留：getTodoList，别改
- 保留 getTodoList
- 不要动数据库
- 保留函数名 getTodoList
- 不要改后端
- 当前负责人是王五
- 当前 focus 是首页待办列表
- 当前截止是月底前

## 状态更新

- **user.focus**: 当前关注点是首页这个列表，别的先不做。 → 当前关注点还是首页这个列表，别的先不做。
- **user.schedule**: 原定截止时间不明确。 → 截止时间改为月底前交就行。
- **user.owner**: 原负责人未明确。 → 负责人临时换成王五。

## 冲突 / 待确认

（无）

## 抽取事件（前 20 条）

- #1 [decision] 当前 focus 就是首页这个列表，别的先不做。
- #2 [decision] 截止改为月底前交就行。
- #3 [decision] 负责人临时换成王五。