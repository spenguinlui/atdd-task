---
description: 記錄問題並建立 Fix 任務，繼續測試
---

# Test Fix: $ARGUMENTS

## 概述

當 E2E 測試發現問題時，自動建立 Fix 任務（含截圖、重現步驟），然後繼續執行剩餘測試。

## 參數解析

`$ARGUMENTS` = 問題描述（必填）

如果沒有提供描述：
```
⚠️ 請提供問題描述
用法：/test-fix {問題描述}
範例：/test-fix 發票金額顯示為負數
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
runs/{timestamp}/recordings/{scenario}-issue-{issue_id}.png
```

**舊結構**：
```
screenshots/{scenario}-issue-{timestamp}.png
```

### Step 3: 建立問題記錄

生成問題 ID（ISS-{序號}）

**新結構**：更新 `runs/{timestamp}/run.yml`：
```yaml
issues:
  - id: "ISS-001"
    severity: "high"
    scenario: "{scenario_id}"
    step: "{step_id}"
    description: "{$ARGUMENTS}"
    screenshot: "recordings/{filename}"
    timestamp: "{ISO timestamp}"
    fixTask: "{fix_task_id}"
```

**舊結構**：更新 `results.yml`：
```yaml
issues:
  - id: "ISS-001"
    severity: "high"
    scenario: "{scenario_id}"
    step: "{step_id}"
    description: "{$ARGUMENTS}"
    screenshot: "screenshots/{filename}"
    timestamp: "{ISO timestamp}"
    fixTask: "{fix_task_id}"
```

### Step 4: 建立 Fix 任務

透過 `atdd_task_create()` 建立新的 Fix 任務：

```json
{
  "id": "{uuid}",
  "type": "fix",
  "description": "[E2E] {問題描述}",
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
    "background": "E2E 測試發現問題",
    "screenshot": "tests/{project}/{test_id}/screenshots/{filename}",
    "reproSteps": [
      "測試場景：{scenario_title}",
      "步驟 {step}：{step_description}",
      "預期：{expected}",
      "實際：{問題描述}"
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

執行 `shared/kanban-operations.md` 的「新增卡片」，在 Requirement 欄位新增 Fix 卡片。

### Step 6: 更新測試記錄

更新 `results.yml`：
```yaml
issues:
  - id: "ISS-001"
    fixTask: "{fix_task_id}"
```

### Step 7: 輸出結果

```markdown
┌──────────────────────────────────────────────────────────────┐
│ 🎫 Fix 任務已建立                                            │
├──────────────────────────────────────────────────────────────┤
│ 📍 問題位置：{場景名稱} - Step {step}                        │
│ 📝 問題描述：{$ARGUMENTS}                                    │
│ 📷 截圖：screenshots/{filename}                              │
│ 🆔 問題 ID：ISS-001                                          │
│ 🎫 Fix 任務：{fix_task_id}                                   │
│                                                              │
│ 📋 複製此命令到新對話窗執行：                                │
│ /fix {project}, {$ARGUMENTS}                                 │
│                                                              │
│ 繼續執行測試...                                              │
└──────────────────────────────────────────────────────────────┘
```

### Step 8: 繼續測試

呼叫 tester Agent 繼續執行剩餘測試。

## 範例

```
/test-fix 發票金額顯示為負數
```

輸出：
```
┌──────────────────────────────────────────────────────────────┐
│ 🎫 Fix 任務已建立                                            │
├──────────────────────────────────────────────────────────────┤
│ 📍 問題位置：S2-建立新期間 - Step 5                          │
│ 📝 問題描述：發票金額顯示為負數                              │
│ 📷 截圖：screenshots/S2-issue-20240115103520.png            │
│ 🆔 問題 ID：ISS-001                                          │
│ 🎫 Fix 任務：e5f6a7b8-c9d0-1234-ef56-789012345678            │
│                                                              │
│ 📋 複製此命令到新對話窗執行：                                │
│ /fix core_web, 發票金額顯示為負數                            │
│                                                              │
│ 繼續執行測試...                                              │
└──────────────────────────────────────────────────────────────┘
```
