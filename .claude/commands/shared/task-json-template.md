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

- `causedBy`: 調查階段才填寫，非建立時。Specist 可用 `git blame` → commit → 反查 task JSON 的 `context.commitHash` 來追溯
- `rootCauseType`: 分類 bug 根因，用於統計分析
- `discoveredIn`: 在哪個環節發現，用於計算 Escape Rate
- Feature/Refactor/Test 任務的 `causation` 保持 null

## Completed 任務 JSON（額外欄位）

```json
{
  "status": "completed",
  "metrics": {
    "totalTools": 114,
    "totalTokens": "18.2M",
    "duration": "2h 30m",
    "totalToolBreakdown": {
      "Read": 35,
      "Edit": 28,
      "Bash": 22,
      "Grep": 15,
      "Write": 8,
      "Glob": 6
    },
    "agents": {
      "specist": { "tools": 14, "tokens": "2.1k" },
      "tester": { "tools": 8, "tokens": "1.4k" },
      "coder": { "tools": 31, "tokens": "2.5k" },
      "gatekeeper": { "tools": 38, "tokens": "10.3k" }
    }
  },
  "completedAt": "{ISO timestamp}"
}
```

## Epic 子任務 JSON（額外欄位）

```json
{
  "epic": {
    "id": "{epic-id}",
    "taskId": "{task-id}",
    "phase": "{phase name}",
    "requirementPath": "requirements/{project}/{epic-id}-{short_name}.md",
    "baReportPath": "requirements/{project}/{epic-id}-{short_name}-ba.md"
  }
}
```

**重要**：`requirementPath` 和 `baReportPath` 從 `epic.yml` 的 `requirement` 區塊取得。這些路徑確保子任務在新對話中仍能定位 Epic 層級的需求文件，維持業務規則的一致性。

Epic 子任務建立時，`metadata` 額外包含 `epic` 欄位：
```
atdd_task_create(
  ...standard_fields,
  metadata: { ...standard_metadata, "epic": { "id": "...", "taskId": "...", ... } }
)
```

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
