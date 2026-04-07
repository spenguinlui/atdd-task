---
description: 標記當前 E2E 測試失敗並停止
---

# Test Fail: $ARGUMENTS

## 概述

標記當前 E2E 測試為失敗，停止測試執行，並記錄失敗原因。

## 執行步驟

### Step 1: 找到當前測試

```
1. 掃描 tests/*/*/test.yml
2. 找到 execution.status == "running" 或 "paused" 的測試
3. 如果沒有，報錯
```

### Step 2: 截圖保存現場

使用 Chrome MCP 截圖：
```
screenshots/{scenario}-fail-{timestamp}.png
```

### Step 3: 更新測試狀態

更新 `test.yml`：

```yaml
execution:
  status: "failed"

results:
  summary:
    failed: {+1}

  scenarios:
    - id: "{scenario_id}"
      status: "failed"
      error:
        step: "{step_id}"
        message: "{$ARGUMENTS 或 '測試失敗'}"
        screenshot: "screenshots/{filename}"
        timestamp: "{ISO timestamp}"
```

### Step 4: 更新任務 JSON

透過 `atdd_task_update()` 更新任務：
```json
{
  "status": "gate",
  "workflow": {
    "currentAgent": "gatekeeper"
  },
  "history": [
    ...existing,
    { "phase": "gate", "timestamp": "{ISO timestamp}" }
  ]
}
```

### Step 5: 輸出失敗訊息

```markdown
┌──────────────────────────────────────────────────────────────┐
│ ❌ 測試已標記失敗                                            │
├──────────────────────────────────────────────────────────────┤
│ 📍 失敗位置：{場景名稱} - Step {step}                        │
│ ⏰ 失敗時間：{timestamp}                                     │
│ 📝 原因：{reason}                                            │
│ 📷 截圖：screenshots/{filename}                              │
│                                                              │
│ 測試統計：                                                   │
│   • 通過：{passed} 個場景                                    │
│   • 失敗：{failed} 個場景                                    │
│   • 跳過：{skipped} 個場景                                   │
│                                                              │
│ 📝 輸入 /continue 進入 Gate 審查                             │
│    輸入 /test-fix 開 Fix 票記錄問題                          │
└──────────────────────────────────────────────────────────────┘
```

## 範例

```
/test-fail 發票金額計算錯誤
```

輸出：
```
┌──────────────────────────────────────────────────────────────┐
│ ❌ 測試已標記失敗                                            │
├──────────────────────────────────────────────────────────────┤
│ 📍 失敗位置：S2-建立新期間 - Step 5                          │
│ ⏰ 失敗時間：2024-01-15 10:35:20                             │
│ 📝 原因：發票金額計算錯誤                                    │
│ 📷 截圖：screenshots/S2-fail-20240115103520.png             │
│                                                              │
│ 測試統計：                                                   │
│   • 通過：1 個場景                                           │
│   • 失敗：1 個場景                                           │
│   • 跳過：0 個場景                                           │
│                                                              │
│ 📝 輸入 /continue 進入 Gate 審查                             │
│    輸入 /test-fix 開 Fix 票記錄問題                          │
└──────────────────────────────────────────────────────────────┘
```
