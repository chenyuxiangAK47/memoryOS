# Memory Guard — 导入摘要

**来源文件**: `D:\Myfile\memoryos\测试的markdown\测试用的markdown.md`

**lines_processed**: 40442
**chunks**: 21
**events_extracted**: 6
**state_updates**: 0
**constraints**: 3
**conflicts**: 0

## 当前有效状态

- **event.latest**: 当前待定位置为vlandia

## 关键约束

- 还是只做了加钱加兵但没设置出生点，所以看起来“没生效”
- **建议**：应该将 `ApplyPresetOrigin()` 移到 `OnCharacterCreationIsOver`，`OnSessionLaunch
- 2) OnSessionLaunched 只做菜单注册/初始化，不做出身 Apply；

## 状态更新

（无）

## 冲突 / 待确认

（无）

## 抽取事件（前 20 条）

- #1 [todo] 请Cursor回答侠义骑士node点击后保存的内容及保存位置，必问问题1。
- #2 [todo] 请Cursor回答Apply出身效果在哪个事件执行并检查是否被覆盖，必问问题2。
- #3 [todo] 请Cursor确认ApplySelectedPreset的switch/case是否命中侠义骑士分支，必问问题3。
- #4 [todo] 询问OriginSystemCampaignBehavior是否被AddBehavior进Campaign，强烈建议问。
- #5 [todo] 询问库塞特“逃奴”出生点传送逻辑的执行时机，强烈建议问。
- #6 [fact] 当前待定位置为vlandia