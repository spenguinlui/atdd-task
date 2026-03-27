# 任務 JSON 模板

## 標準任務 JSON

```json
{
  "id": "{uuid}",
  "type": "{feature|fix|refactor|test}",
  "description": "{標題}",
  "status": "requirement",
  "projectId": "{project}",
  "projectName": "{project}",
  "domain": "",
  "git": {
    "branch": "{selected_branch}"
  },
  "agents": [],
  "workflow": {
    "mode": "guided",
    "currentAgent": "specist",
    "confidence": 0,
    "pendingAction": null
  },
  "acceptance": {
    "profile": null,
    "testLayers": {},
    "fixture": null,
    "results": {},
    "verificationGuide": null
  },
  "history": [
    { "phase": "requirement", "timestamp": "{ISO timestamp}" }
  ],
  "jira": {
    "issueKey": null,
    "url": null
  },
  "context": {
    "background": "",
    "relatedDomains": [],
    "deletedFiles": [],
    "modifiedFiles": [],
    "changes": [],
    "commitHash": ""
  },
  "metrics": null,
  "createdAt": "{ISO timestamp}",
  "updatedAt": "{ISO timestamp}"
}
```

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

## 儲存位置

```
tasks/{project}/active/{uuid}.json   # 進行中
tasks/{project}/completed/{uuid}.json # 已完成
tasks/{project}/failed/{uuid}.json   # 失敗
```

## 產生 UUID

```bash
uuidgen | tr '[:upper:]' '[:lower:]'
```
