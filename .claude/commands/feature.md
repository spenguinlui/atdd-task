---
description: 啟動新功能開發任務（Guided 模式）
---

# Feature Task: $ARGUMENTS

## 解析參數

格式：`{project}, {標題}`

有效專案：`sf_project`, `core_web`, `core_web_frontend`, `digiwin_erp`, `stock_commentary`, `jv_project`

---

## 執行步驟（嚴格按順序，不得增加額外步驟）

1. **Git Branch 選擇**：參考 `shared/git-branch-selection.md`，建議命名 `feature/{short-description}`
2. **Epic 子任務偵測**：參考 `shared/epic-task-flow.md`
3. **建立任務 JSON**：參考 `shared/task-json-template.md`，type=feature
4. **更新 Kanban**：執行 `shared/kanban-operations.md` 的「新增卡片」（含 Jira 開票確認）
5. **回寫 Jira Issue Key**（僅選擇開立 Jira 票時）：從 kanban-adapter.sh 輸出解析 issue key（格式 `✓ Jira issue created: {KEY} —`），寫入任務 JSON 的 `jira.issueKey` 和 `jira.url`（`{base_url}/browse/{KEY}`）
6. **輸出任務建立訊息**：類型、專案、標題、ID、Jira 連結（若有）
7. **立即呼叫 specist Agent**（見下方）

⛔ **步驟 1-6 期間禁止讀取**：domain 知識、既有 requirement/spec、程式碼。這些全部是 specist 的職責。main 只做任務建立，不做需求研究。

---

## 呼叫 specist Agent（Step 7）

參考：`shared/agent-call-patterns.md`

**Prompt 重點**：
- Domain 識別（讀取 domain-registry.md）
- 跨 Domain 影響分析
- 信心度評估（需達 95%）
- 範圍評估（判斷是否上升 Epic）
- 選擇 ATDD Profile
- 撰寫 Given-When-Then 規格

---

## 任務流程

參考：`shared/task-flow-diagrams.md` - Feature 流程

```
requirement → specification → testing → development → review → gate
```

**Feature 特點**：信心度 95%、完整 specification、範圍評估、雙 reviewer

---

## Gate 後知識策展

> 知識策展邏輯已統一由 `/continue` 命令處理（Step 2.5）。
> 適用於所有任務類型，無需在各任務命令中重複定義。
