---
description: 記錄問題並建立 Fix 任務，停止測試
---

# Test Fix Stop: $ARGUMENTS

## 概述

當 E2E 測試發現嚴重問題時，自動建立 Fix 任務（含截圖、重現步驟），然後停止測試執行。

這與 `/test-fix` 的差異是：此命令會**停止測試**，適用於發現的問題導致後續測試無法繼續的情況。

## 參數解析

`$ARGUMENTS` = 問題描述（必填）

如果沒有提供描述：
```
⚠️ 請提供問題描述
用法：/test-fix-stop {問題描述}
範例：/test-fix-stop 系統崩潰無法繼續
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
    severity: "critical"
    scenario: "{scenario_id}"
    step: "{step_id}"
    description: "{$ARGUMENTS}"
    screenshot: "recordings/{filename}"
    timestamp: "{ISO timestamp}"
    fixTask: "{fix_task_id}"
    blocking: true
```

**舊結構**：更新 `results.yml`：
```yaml
issues:
  - id: "ISS-001"
    severity: "critical"
    scenario: "{scenario_id}"
    step: "{step_id}"
    description: "{$ARGUMENTS}"
    screenshot: "screenshots/{filename}"
    timestamp: "{ISO timestamp}"
    fixTask: "{fix_task_id}"
    blocking: true
```

### Step 4: 建立 Fix 任務

透過 `atdd_task_create()` 建立新的 Fix 任務：

```json
{
  "id": "{uuid}",
  "type": "fix",
  "description": "[E2E Critical] {問題描述}",
  "status": "requirement",
  "projectId": "{project}",
  "projectName": "{project}",
  "domain": "{test_domain}",
  "sourceTest": {
    "testId": "{test_id}",
    "scenario": "{scenario_id}",
    "step": "{step_id}",
    "issueId": "ISS-001",
    "blocking": true
  },
  "agents": [],
  "workflow": {
    "mode": "guided",
    "currentAgent": "specist",
    "confidence": 0
  },
  "context": {
    "background": "E2E 測試發現嚴重問題（阻斷）",
    "screenshot": "tests/{project}/{test_id}/screenshots/{filename}",
    "reproSteps": [
      "測試場景：{scenario_title}",
      "步驟 {step}：{step_description}",
      "預期：{expected}",
      "實際：{問題描述}",
      "影響：阻斷後續測試"
    ]
  },
  "history": [
    { "phase": "requirement", "timestamp": "{ISO timestamp}" }
  ],
  "createdAt": "{ISO timestamp}",
  "updatedAt": "{ISO timestamp}"
}
```

### Step 5: 更新測試狀態

**新結構**：更新 `runs/{timestamp}/run.yml`：
```yaml
status: "failed"
completedAt: "{ISO timestamp}"

results:
  failed: {+1}

issues:
  - id: "ISS-001"
    blocking: true
    fixTask: "{fix_task_id}"
```

同時更新 `suite.yml` 的 stats：
```yaml
stats:
  lastRun: "{ISO timestamp}"
  lastStatus: "failed"
```

**舊結構**：更新 `test.yml`：
```yaml
execution:
  status: "failed"

results:
  summary:
    failed: {+1}

  issues:
    - id: "ISS-001"
      blocking: true
      fixTask: "{fix_task_id}"
```

### Step 6: 更新 Kanban

執行 `shared/kanban-operations.md` 的「新增卡片」，在 Requirement 欄位新增 Fix 卡片（標記為 critical）。

### Step 7: 更新任務 JSON

透過 `atdd_task_update()` 更新任務：
```json
{
  "status": "gate",
  "workflow": {
    "currentAgent": "gatekeeper"
  }
}
```

### Step 8: 輸出結果

```markdown
┌──────────────────────────────────────────────────────────────┐
│ 🎫 Fix 任務已建立（測試已停止）                              │
├──────────────────────────────────────────────────────────────┤
│ 📍 問題位置：{場景名稱} - Step {step}                        │
│ 📝 問題描述：{$ARGUMENTS}                                    │
│ ⚠️ 嚴重度：Critical（阻斷）                                  │
│ 📷 截圖：screenshots/{filename}                              │
│ 🆔 問題 ID：ISS-001                                          │
│ 🎫 Fix 任務：{fix_task_id}                                   │
│                                                              │
│ 📋 複製此命令到新對話窗執行：                                │
│ /fix {project}, {$ARGUMENTS}                                 │
│                                                              │
│ 測試統計：                                                   │
│   • 通過：{passed} 個場景                                    │
│   • 失敗：{failed} 個場景                                    │
│   • 跳過：{skipped} 個場景                                   │
│   • 未執行：{remaining} 個場景                               │
│                                                              │
│ 📝 修復後輸入 /test-resume 繼續測試                          │
│ 📝 或輸入 /continue 進入 Gate 審查                           │
└──────────────────────────────────────────────────────────────┘
```

## 範例

```
/test-fix-stop 系統崩潰無法繼續
```

輸出：
```
┌──────────────────────────────────────────────────────────────┐
│ 🎫 Fix 任務已建立（測試已停止）                              │
├──────────────────────────────────────────────────────────────┤
│ 📍 問題位置：S2-建立新期間 - Step 3                          │
│ 📝 問題描述：系統崩潰無法繼續                                │
│ ⚠️ 嚴重度：Critical（阻斷）                                  │
│ 📷 截圖：screenshots/S2-issue-20240115103520.png            │
│ 🆔 問題 ID：ISS-001                                          │
│ 🎫 Fix 任務：e5f6a7b8-c9d0-1234-ef56-789012345678            │
│                                                              │
│ 📋 複製此命令到新對話窗執行：                                │
│ /fix core_web, 系統崩潰無法繼續                              │
│                                                              │
│ 測試統計：                                                   │
│   • 通過：1 個場景                                           │
│   • 失敗：1 個場景                                           │
│   • 跳過：0 個場景                                           │
│   • 未執行：2 個場景                                         │
│                                                              │
│ 📝 修復後輸入 /test-resume 繼續測試                          │
│ 📝 或輸入 /continue 進入 Gate 審查                           │
└──────────────────────────────────────────────────────────────┘
```
