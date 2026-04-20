---
description: 啟動重構任務（確保不破壞現有功能）
---

# Refactor Task: $ARGUMENTS

## 解析參數

格式：`{project}, {標題}`

有效專案：見 `.claude/config/projects.yml`

---

## 執行步驟（嚴格按順序，不得增加額外步驟）

1. **Jira 確認**：執行 `shared/jira-operations.md` 的「Jira 開票確認」（三選一：否、是、已有 Jira 票），取得 Jira 決定和 issue key（如有）
2. **Git Branch 選擇**：參考 `shared/git-branch-selection.md`，詢問要在 master 開發還是建立新分支（建議命名 `refactor/{short-description}`）
3. **Epic 子任務偵測**：參考 `shared/epic-task-flow.md`
4. **建立任務 JSON**：參考 `shared/task-json-template.md`，type=refactor
5. **回寫 Jira Issue Key**（選擇「是」或「已有 Jira 票」時）：新建票從 kanban-adapter.sh 輸出解析 issue key（格式 `✓ Jira issue created: {KEY} —`），貼上連結則直接使用解析結果。寫入任務 JSON 的 `jira.issueKey`、`jira.url`（`{base_url}/browse/{KEY}`）和 `jira.source`（`"created"` 或 `"linked"`），並同步 MCP：`atdd_task_update(task_id, metadata={"jira": {"issueKey": "{KEY}", "url": "{url}", "source": "{created|linked}"}})`
6. **輸出任務建立訊息**：類型、專案、標題、ID、Jira 連結（若有）
7. **立即呼叫 specist Agent**（見下方）

⛔ **步驟 1-6 期間禁止讀取**：domain 知識、既有 requirement/spec、程式碼。這些全部是 specist 的職責。main 只做任務建立，不做需求研究。

8. **Rename 對話**（specist 返回後）：輸出建議命令，格式為 `/rename Refactor: {標題}`，方便用戶直接複製貼上重命名對話。

---

## 呼叫 specist Agent（Step 7）

參考：`shared/agent-call-patterns.md`

**Prompt 重點**：
- Domain 識別
- 重構目標和範圍
- 受影響的檔案和模組
- 跨 Domain 影響分析
- 信心度評估（需達 95%）
- 重構規格（目前狀態、預期狀態、不變性約束）

**重構原則**：行為不變、測試通過、小步前進

---

## 任務流程

參考：`shared/task-flow-diagrams.md`

```
requirement → testing → development → review → gate
```

**Refactor 特點**：先確認現有測試、只有 style-reviewer、確認行為不變性

---

## 重構類型參考

| 類型 | 關鍵字 | 風險 |
|------|--------|------|
| Extract Method | 提取、拆分方法 | Low |
| Extract Class | 拆分類別 | Medium |
| Rename | 重命名 | Low |
| Move | 移動 | Medium |
| Replace | 替換 | High |
