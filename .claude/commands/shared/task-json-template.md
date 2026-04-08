# 任務 JSON 模板

## 建立任務（MCP 為唯一資料來源）

### Step A: 呼叫 MCP 建立任務

```
atdd_task_create(
  project: "{project}",
  type: "{feature|fix|refactor|test}",
  description: "{標題}",
  metadata: {
    "git": { "branch": "{selected_branch}" },
    "workflow": { "mode": "guided", "currentAgent": "specist", "confidence": 0, "pendingAction": null },
    "acceptance": { "profile": null, "testLayers": {}, "fixture": null, "results": {}, "verificationGuide": null },
    "jira": { "issueKey": null, "url": null, "source": null },
    "context": { "background": "", "relatedDomains": [], "deletedFiles": [], "modifiedFiles": [], "changes": [], "commitHash": "" }
  }
)
```

- Fix 任務額外傳入 `causation` 參數（見下方 Causation 欄位說明）
- 從回傳結果取得 `id` 作為任務 UUID

### Step B: 記錄 History（MCP）

```
atdd_task_add_history(
  task_id: "{id}",
  phase: "requirement",
  status: "requirement",
  note: "Task created via /{type} command"
)
```

---

## MCP 操作參考

> 所有任務狀態透過 MCP tool 寫入 DB：
> - 欄位更新 → `atdd_task_update(task_id, ...changed_fields, metadata={...changed_metadata})`
> - 階段轉移 → `atdd_task_update` + `atdd_task_add_history`
> - Metrics → `atdd_task_add_metrics`
> - 讀取任務 → `atdd_task_get(task_id)` 或 `atdd_task_list()`
>
> **MCP 回傳結構**：
> - `atdd_task_list()` → `{"items": [...], "total": N}`
> - `atdd_task_get(task_id)` → 單一任務物件
> - 所有 task_id 參數必須使用完整 UUID，禁止截斷

---

## Causation 欄位說明（Fix 任務專用）

`causation` 用於追蹤 bug 的因果關係，在 specist 調查階段填寫：

```json
"causation": {
  "causedBy": {
    "taskId": "a8a9f6d2-...",
    "commitHash": "abc123",
    "description": "月結分帳功能"
  },
  "rootCauseType": "feature-defect",
  "discoveredIn": "production",
  "discoveredAt": "2026-04-03T10:00:00Z",
  "timeSinceIntroduced": "32d"
}
```

- `causedBy`: 調查階段才填寫，非建立時。Specist 可用 `git blame` → commit → 透過 `atdd_task_list()` 搜尋 `context.commitHash` 來追溯
- `rootCauseType`: 分類 bug 根因，用於統計分析
- `discoveredIn`: 在哪個環節發現，用於計算 Escape Rate
- Feature/Refactor/Test 任務的 `causation` 保持 null

## Completed 任務額外欄位

結案時透過 `atdd_task_update` 寫入 `status: "completed"`、`completedAt`、`metrics`（含 agents 各項統計）。
詳見 `shared/task-state-update.md` Event 2。

## Epic 子任務額外欄位

metadata 加入 `epic: { id, taskId, phase, requirementPath, baReportPath }`。
路徑從 `epic.yml` 的 `requirement` 區塊取得，確保跨對話能定位 Epic 需求文件。
詳見 `shared/epic-task-flow.md`。

## 任務狀態對照

| 狀態 | 說明 |
|------|------|
| requirement | 需求分析中 |
| specification | 規格撰寫中 |
| testing | 測試生成中 |
| development | 開發中 |
| review | 審查中 |
| gate | 品質門檻檢查 |
| deployed | 已部署待驗證 |
| completed | 已完成 |
| verified | 已驗證 |
| failed/aborted | 失敗/放棄 |
| escaped | 生產問題 |
