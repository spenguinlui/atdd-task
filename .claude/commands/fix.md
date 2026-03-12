---
description: 啟動 Bug 修復任務（簡化流程）
---

# Fix Task: $ARGUMENTS

## 解析參數

格式：`{project}, {標題}`

有效專案：`sf_project`, `core_web`, `core_web_frontend`, `digiwin_erp`, `stock_commentary`, `jv_project`

---

## 執行步驟（嚴格按順序，不得增加額外步驟）

1. **Git Branch 選擇**：參考 `shared/git-branch-selection.md`，建議命名 `fix/{short-description}`
2. **Epic 子任務偵測**：參考 `shared/epic-task-flow.md`
3. **建立任務 JSON**：參考 `shared/task-json-template.md`，type=fix
4. **更新 Kanban**：執行 `shared/kanban-operations.md` 的「新增卡片」（含 Jira 開票確認）
5. **回寫 Jira Issue Key**（僅選擇開立 Jira 票時）：從 kanban-adapter.sh 輸出解析 issue key（格式 `✓ Jira issue created: {KEY} —`），寫入任務 JSON 的 `jira.issueKey` 和 `jira.url`（`{base_url}/browse/{KEY}`）
6. **輸出任務建立訊息**：類型、專案、標題、ID、Jira 連結（若有）
7. **立即呼叫 specist Agent**（見下方）

⛔ **步驟 1-6 期間禁止讀取**：domain 知識、既有 requirement/spec、程式碼。這些全部是 specist 的職責。main 只做任務建立，不做需求研究。

---

## 呼叫 specist Agent（Step 7）

參考：`shared/agent-call-patterns.md`

**Prompt 重點**：
- Domain 識別
- Bug 現象和預期行為
- 信心度評估（門檻 95%）
- 如需更多資訊：重現步驟、預期 vs 實際、錯誤訊息
- 撰寫簡化規格（Bug 描述 + 預期修復行為）

---

## 任務流程

參考：`shared/task-flow-diagrams.md` - Fix 流程

```
requirement → testing → development → review → gate
```

**Fix 特點**：跳過 specification、只有 risk-reviewer、流程更快
