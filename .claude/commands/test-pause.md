---
description: 暫停當前 E2E 測試，等待人工介入
---

# Test Pause: $ARGUMENTS

## 概述

暫停當前執行中的 E2E 測試，等待人工介入。測試狀態會被保存，稍後可用 `/test-resume` 繼續。

## 執行步驟

### Step 1: 找到當前執行中的測試

```
搜尋順序：
1. 新結構：tests/{project}/suites/*/runs/latest/run.yml
   - 找到 status == "running" 的執行記錄
2. 舊結構：tests/{project}/{uuid}/test.yml（向下相容）
   - 找到 execution.status == "running" 的測試
3. 如果沒有執行中的測試，報錯
```

如果沒有執行中的測試：
```
⚠️ 沒有執行中的測試可暫停
```

### Step 2: 更新測試狀態

**新結構**：更新 `runs/{timestamp}/run.yml`：
```yaml
status: "paused"
pause:
  reason: "{$ARGUMENTS 或 '用戶請求暫停'}"
  timestamp: "{ISO timestamp}"
  currentScenario: "{當前場景}"
  currentStep: "{當前步驟}"
  resumable: true
```

**舊結構**：更新 `test.yml`：
```yaml
execution:
  status: "paused"
  currentScenario: "{當前場景}"
  currentStep: "{當前步驟}"
  pause:
    reason: "{$ARGUMENTS 或 '用戶請求暫停'}"
    timestamp: "{ISO timestamp}"
    resumable: true
```

### Step 3: 截圖保存現場

使用 Chrome MCP 截圖：

**新結構**：
```
runs/{timestamp}/recordings/{scenario}-pause.png
```

**舊結構**：
```
screenshots/{scenario}-pause-{timestamp}.png
```

### Step 4: 更新任務 JSON

透過 `atdd_task_update()` 更新任務：
```json
{
  "status": "testing",
  "workflow": {
    "pendingAction": "paused"
  }
}
```

### Step 5: 輸出暫停訊息

```markdown
┌──────────────────────────────────────────────────────────────┐
│ ⏸️ 測試已暫停                                                │
├──────────────────────────────────────────────────────────────┤
│ 📍 暫停位置：{場景名稱} - Step {step}                        │
│ ⏰ 暫停時間：{timestamp}                                     │
│ 📝 原因：{reason}                                            │
│ 📷 截圖：screenshots/{filename}                              │
│                                                              │
│ 📝 輸入 /test-resume 繼續測試                                │
│    輸入 /test-fail 標記失敗                                  │
│    輸入 /test-skip 跳過當前步驟                              │
└──────────────────────────────────────────────────────────────┘
```

## 範例

```
/test-pause 等待確認資料是否正確
```

輸出：
```
┌──────────────────────────────────────────────────────────────┐
│ ⏸️ 測試已暫停                                                │
├──────────────────────────────────────────────────────────────┤
│ 📍 暫停位置：S2-建立新期間 - Step 3                          │
│ ⏰ 暫停時間：2024-01-15 10:30:45                             │
│ 📝 原因：等待確認資料是否正確                                │
│ 📷 截圖：screenshots/S2-pause-20240115103045.png            │
│                                                              │
│ 📝 輸入 /test-resume 繼續測試                                │
│    輸入 /test-fail 標記失敗                                  │
│    輸入 /test-skip 跳過當前步驟                              │
└──────────────────────────────────────────────────────────────┘
```
