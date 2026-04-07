---
description: 記錄缺少功能並建立 Feature 任務，繼續測試
---

# Test Feature: $ARGUMENTS

## 概述

當 E2E 測試發現缺少功能（不是 bug，是尚未實作的需求）時，自動建立 Feature 任務，然後繼續執行剩餘測試。

## 參數解析

`$ARGUMENTS` = 功能描述（必填）

如果沒有提供描述：
```
⚠️ 請提供功能描述
用法：/test-feature {功能描述}
範例：/test-feature 缺少批次匯出功能
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
runs/{timestamp}/recordings/{scenario}-feature-{issue_id}.png
```

**舊結構**：
```
screenshots/{scenario}-feature-{timestamp}.png
```

### Step 3: 建立問題記錄

生成問題 ID（ISS-{序號}）

**新結構**：更新 `runs/{timestamp}/run.yml`：
```yaml
issues:
  - id: "ISS-001"
    type: "feature_request"
    severity: "medium"
    scenario: "{scenario_id}"
    step: "{step_id}"
    description: "{$ARGUMENTS}"
    screenshot: "recordings/{filename}"
    timestamp: "{ISO timestamp}"
    featureTask: "{feature_task_id}"
```

**舊結構**：更新 `results.yml`：
```yaml
issues:
  - id: "ISS-001"
    type: "feature_request"
    severity: "medium"
    scenario: "{scenario_id}"
    step: "{step_id}"
    description: "{$ARGUMENTS}"
    screenshot: "screenshots/{filename}"
    timestamp: "{ISO timestamp}"
    featureTask: "{feature_task_id}"
```

### Step 4: 建立 Feature 任務

透過 `atdd_task_create()` 建立新的 Feature 任務：

```json
{
  "id": "{uuid}",
  "type": "feature",
  "description": "[E2E Feature] {功能描述}",
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
    "background": "E2E 測試發現缺少功能",
    "screenshot": "tests/{project}/{suite-id}/runs/{timestamp}/recordings/{filename}",
    "reproSteps": [
      "測試場景：{scenario_title}",
      "步驟 {step}：{step_description}",
      "預期：{expected}",
      "實際：功能不存在 - {功能描述}"
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

執行 `shared/kanban-operations.md` 的「新增卡片」，在 Requirement 欄位新增 Feature 卡片。

### Step 6: 更新測試記錄

更新 run.yml / results.yml：
```yaml
issues:
  - id: "ISS-001"
    featureTask: "{feature_task_id}"
```

### Step 7: 輸出結果

```markdown
┌──────────────────────────────────────────────────────────────┐
│ 📋 Feature 任務已建立                                        │
├──────────────────────────────────────────────────────────────┤
│ 📍 發現位置：{場景名稱} - Step {step}                        │
│ 📝 功能描述：{$ARGUMENTS}                                    │
│ 📷 截圖：recordings/{filename}                               │
│ 🆔 問題 ID：ISS-001                                          │
│ 📋 Feature 任務：{feature_task_id}                            │
│                                                              │
│ 📋 複製此命令到新對話窗執行：                                │
│ /feature {project}, {$ARGUMENTS}                             │
│                                                              │
│ 繼續執行測試...                                              │
└──────────────────────────────────────────────────────────────┘
```

### Step 8: 繼續測試

呼叫 tester Agent 繼續執行剩餘測試。

## 範例

```
/test-feature 缺少批次匯出功能
```

輸出：
```
┌──────────────────────────────────────────────────────────────┐
│ 📋 Feature 任務已建立                                        │
├──────────────────────────────────────────────────────────────┤
│ 📍 發現位置：S3-匯出報表 - Step 4                            │
│ 📝 功能描述：缺少批次匯出功能                                │
│ 📷 截圖：recordings/S3-feature-ISS-002.png                  │
│ 🆔 問題 ID：ISS-002                                          │
│ 📋 Feature 任務：a1b2c3d4-e5f6-7890-abcd-ef1234567890        │
│                                                              │
│ 📋 複製此命令到新對話窗執行：                                │
│ /feature core_web, 缺少批次匯出功能                          │
│                                                              │
│ 繼續執行測試...                                              │
└──────────────────────────────────────────────────────────────┘
```
