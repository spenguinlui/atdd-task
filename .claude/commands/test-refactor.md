---
description: 記錄架構問題並建立 Refactor 任務，繼續測試
---

# Test Refactor: $ARGUMENTS

## 概述

當 E2E 測試發現架構問題（不是 bug，是需要重構的技術債）時，自動建立 Refactor 任務，然後繼續執行剩餘測試。

## 參數解析

`$ARGUMENTS` = 架構問題描述（必填）

如果沒有提供描述：
```
⚠️ 請提供架構問題描述
用法：/test-refactor {問題描述}
範例：/test-refactor 頁面載入過慢，需要分頁或懶載入
```

## 執行步驟

### Step 1: 找到當前測試

```
搜尋順序：
1. 新結構：tests/{project}/suites/*/runs/latest/run.yml
   - 找到 status == "running" 或 "paused" 的執行記錄
2. 舊結構：tests/{project}/{uuid}/test.yml（向下相容）
   - 找到 execution.status == "running" 或 "paused" 的測試
3. 如果沒有，報錯
```

### Step 2: 截圖保存現場

使用 Chrome MCP 截圖：

**新結構**：
```
runs/{timestamp}/recordings/{scenario}-refactor-{issue_id}.png
```

**舊結構**：
```
screenshots/{scenario}-refactor-{timestamp}.png
```

### Step 3: 建立問題記錄

生成問題 ID（ISS-{序號}）

**新結構**：更新 `runs/{timestamp}/run.yml`：
```yaml
issues:
  - id: "ISS-001"
    type: "refactor_request"
    severity: "medium"
    scenario: "{scenario_id}"
    step: "{step_id}"
    description: "{$ARGUMENTS}"
    screenshot: "recordings/{filename}"
    timestamp: "{ISO timestamp}"
    refactorTask: "{refactor_task_id}"
```

**舊結構**：更新 `results.yml`：
```yaml
issues:
  - id: "ISS-001"
    type: "refactor_request"
    severity: "medium"
    scenario: "{scenario_id}"
    step: "{step_id}"
    description: "{$ARGUMENTS}"
    screenshot: "screenshots/{filename}"
    timestamp: "{ISO timestamp}"
    refactorTask: "{refactor_task_id}"
```

### Step 4: 建立 Refactor 任務

透過 `atdd_task_create()` 建立新的 Refactor 任務：

```json
{
  "id": "{uuid}",
  "type": "refactor",
  "description": "[E2E Refactor] {問題描述}",
  "status": "requirement",
  "projectId": "{project}",
  "projectName": "{project}",
  "domain": "{test_domain}",
  "sourceTest": {
    "testId": "{test_id}",
    "scenario": "{scenario_id}",
    "step": "{step_id}",
    "issueId": "ISS-001"
  },
  "agents": [],
  "workflow": {
    "mode": "guided",
    "currentAgent": "specist",
    "confidence": 0
  },
  "context": {
    "background": "E2E 測試發現架構問題需要重構",
    "screenshot": "tests/{project}/{suite-id}/runs/{timestamp}/recordings/{filename}",
    "reproSteps": [
      "測試場景：{scenario_title}",
      "步驟 {step}：{step_description}",
      "觀察：{問題描述}",
      "建議：需要重構改善"
    ]
  },
  "history": [
    { "phase": "requirement", "timestamp": "{ISO timestamp}" }
  ],
  "createdAt": "{ISO timestamp}",
  "updatedAt": "{ISO timestamp}"
}
```

### Step 5: 更新 Kanban

執行 `shared/kanban-operations.md` 的「新增卡片」，在 Requirement 欄位新增 Refactor 卡片。

### Step 6: 更新測試記錄

更新 run.yml / results.yml：
```yaml
issues:
  - id: "ISS-001"
    refactorTask: "{refactor_task_id}"
```

### Step 7: 輸出結果

```markdown
┌──────────────────────────────────────────────────────────────┐
│ 🔧 Refactor 任務已建立                                       │
├──────────────────────────────────────────────────────────────┤
│ 📍 發現位置：{場景名稱} - Step {step}                        │
│ 📝 問題描述：{$ARGUMENTS}                                    │
│ 📷 截圖：recordings/{filename}                               │
│ 🆔 問題 ID：ISS-001                                          │
│ 🔧 Refactor 任務：{refactor_task_id}                          │
│                                                              │
│ 📋 複製此命令到新對話窗執行：                                │
│ /refactor {project}, {$ARGUMENTS}                            │
│                                                              │
│ 繼續執行測試...                                              │
└──────────────────────────────────────────────────────────────┘
```

### Step 8: 繼續測試

呼叫 tester Agent 繼續執行剩餘測試。

## 範例

```
/test-refactor 頁面載入過慢，需要分頁或懶載入
```

輸出：
```
┌──────────────────────────────────────────────────────────────┐
│ 🔧 Refactor 任務已建立                                       │
├──────────────────────────────────────────────────────────────┤
│ 📍 發現位置：S4-帳單列表 - Step 2                            │
│ 📝 問題描述：頁面載入過慢，需要分頁或懶載入                  │
│ 📷 截圖：recordings/S4-refactor-ISS-003.png                 │
│ 🆔 問題 ID：ISS-003                                          │
│ 🔧 Refactor 任務：b2c3d4e5-f6a7-8901-bcde-f23456789012      │
│                                                              │
│ 📋 複製此命令到新對話窗執行：                                │
│ /refactor core_web, 頁面載入過慢，需要分頁或懶載入           │
│                                                              │
│ 繼續執行測試...                                              │
└──────────────────────────────────────────────────────────────┘
```
