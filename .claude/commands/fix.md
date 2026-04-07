---
description: 啟動 Bug 修復任務（簡化流程）
---

# Fix Task: $ARGUMENTS

## 解析參數

格式：`{project}, {標題}`

有效專案：`sf_project`, `core_web`, `core_web_frontend`, `digiwin_erp`, `stock_commentary`, `jv_project`

---

## 執行步驟（嚴格按順序，不得增加額外步驟）

1. **Jira 確認**：執行 `shared/kanban-operations.md` 的「Jira 開票確認」（三選一：否、是、已有 Jira 票），取得 Jira 決定和 issue key（如有）
2. **Git Branch 選擇**：參考 `shared/git-branch-selection.md`，如有 Jira issue key 則自動使用 issue key 作為分支名稱；否則建議命名 `fix/{short-description}`
3. **Epic 子任務偵測**：參考 `shared/epic-task-flow.md`
4. **建立任務 JSON**：參考 `shared/task-json-template.md`，type=fix
5. **更新 Kanban**：執行 `shared/kanban-operations.md` 的「新增卡片」（使用 Step 1 的 Jira 決定，不再重複詢問）
6. **回寫 Jira Issue Key**（選擇「是」或「已有 Jira 票」時）：新建票從 kanban-adapter.sh 輸出解析 issue key（格式 `✓ Jira issue created: {KEY} —`），貼上連結則直接使用解析結果。寫入任務 JSON 的 `jira.issueKey`、`jira.url`（`{base_url}/browse/{KEY}`）和 `jira.source`（`"created"` 或 `"linked"`），並同步 MCP：`atdd_task_update(task_id, metadata={"jira": {"issueKey": "{KEY}", "url": "{url}", "source": "{created|linked}"}})`
6. **輸出任務建立訊息**：類型、專案、標題、ID、Jira 連結（若有）
7. **立即呼叫 specist Agent**（見下方）

⛔ **步驟 1-6 期間禁止讀取**：domain 知識、既有 requirement/spec、程式碼。這些全部是 specist 的職責。main 只做任務建立，不做需求研究。

8. **Rename 對話**（specist 返回後）：輸出建議命令，格式為 `/rename Fix: {標題}`，方便用戶直接複製貼上重命名對話。

---

## 呼叫 specist Agent（Step 7）

參考：`shared/agent-call-patterns.md`

**Prompt 重點**：
- Domain 識別
- Bug 現象和預期行為
- 信心度評估（門檻 95%）
- 如需更多資訊：重現步驟、預期 vs 實際、錯誤訊息
- 撰寫簡化規格（Bug 描述 + 預期修復行為）
- **Causation 調查**（調查階段填寫 task JSON 的 `causation` 欄位）：
  - `discoveredIn`: 問題在哪個環節被發現（production/staging/e2e/review/development）
  - `causedBy`: 嘗試用 `git blame` 問題程式碼行 → 找到 commit → 透過 `atdd_task_list()` 搜尋 `context.commitHash` 匹配的任務。找到則填入 `taskId`、`commitHash`、`description`；找不到則保持 null
  - `rootCauseType`: feature-defect（功能本身缺陷）| fix-regression（修 bug 改壞）| legacy（歷史債務）| unknown | environment | dependency
  - `discoveredAt`: 任務建立時間即為發現時間

---

## 任務流程

參考：`shared/task-flow-diagrams.md` - Fix 流程

```
requirement → testing → development → review → gate
```

**Fix 特點**：跳過 specification、只有 risk-reviewer、流程更快
