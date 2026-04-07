---
description: 修復 Review 發現的 Critical 問題（TDD 流程）
---

# Fix Critical Issues

修復 Review 階段發現的 Critical 嚴重度問題，使用 TDD 流程（先補測試，再實作）。

---

## 前置檢查

1. 確認有 active 任務
2. 確認任務狀態為 `review`
3. 確認 `context.reviewFindings` 存在
4. 確認有 severity 為 `critical` 的問題

**如果沒有 Critical 問題：**
```markdown
┌──────────────────────────────────────────────────────┐
│ ⚠️ 沒有 Critical 問題需要修復                        │
├──────────────────────────────────────────────────────┤
│                                                      │
│ 可選擇：                                             │
│ • /fix-high - 修復 Critical + High 問題             │
│ • /fix-all - 修復所有問題                           │
│ • /continue - 直接進入 gate 階段                    │
│                                                      │
└──────────────────────────────────────────────────────┘
```

---

## 執行步驟

### Step 1: 篩選 Critical 問題

從 `context.reviewFindings.riskReview.findings` 和 `context.reviewFindings.styleReview.issues` 中篩選 `severity === "critical"` 的問題。

### Step 2: 更新任務 JSON

```json
{
  "status": "testing",
  "workflow": {
    "currentAgent": "tester",
    "pendingAction": "fix_review"
  },
  "context": {
    "reviewFindings": {
      "fixScope": "critical"
    }
  },
  "history": [
    // 加入新記錄
    { "phase": "testing", "timestamp": "{ISO}", "reason": "fix-critical" }
  ]
}
```

### Step 3: 更新 Kanban

執行 `shared/kanban-operations.md` 的「移動卡片」

### Step 4: 輸出訊息

```markdown
┌──────────────────────────────────────────────────────┐
│ 📋 修復 Critical 問題                                │
├──────────────────────────────────────────────────────┤
│ 📍 從：review                                        │
│ 📍 到：testing                                       │
│ 🔧 修復範圍：critical only                           │
│                                                      │
│ 💡 可依序輸入：/clear → /continue 清理對話後繼續     │
│                                                      │
│ ═══ 待修復問題 ═══                                   │
│ 1. [SEC-001] 缺乏授權控制                            │
│    └─ use_cases/void_current_invoice.rb:7-14         │
│ 2. [SEC-002] 併發控制不足                            │
│    └─ use_cases/void_current_invoice.rb:7-14         │
│ 3. [SEC-003] 輸入驗證缺失                            │
│    └─ use_cases/void_current_invoice.rb:8            │
│                                                      │
│ 正在啟動 tester 補充測試...                          │
└──────────────────────────────────────────────────────┘
```

### Step 5: 呼叫 tester Agent

```
Task(
  subagent_type: "tester",
  prompt: "
    專案：{project}
    任務：補充測試案例以覆蓋 review 發現的 Critical 問題
    任務 JSON：{task_json_path}
    模式：fix-review

    請執行：
    1. 讀取任務 JSON 的 context.reviewFindings
    2. 篩選 severity === 'critical' 的問題
    3. 為每個問題生成測試案例
       - 使用 testHint 作為測試設計參考
       - 測試應該先失敗（紅燈）
    4. 執行測試確認失敗
    5. 更新任務 JSON 的 context.testFiles

    輸出格式請遵循 tester agent 的標準格式。
  "
)
```

### Step 6: tester 完成後

1. 更新 agents 陣列加入 tester 記錄
2. 更新 status 為 `development`
3. 呼叫 coder agent：

```
Task(
  subagent_type: "coder",
  prompt: "
    專案：{project}
    任務：修復 review 發現的 Critical 問題，讓測試通過
    任務 JSON：{task_json_path}
    模式：fix-review

    請執行：
    1. 讀取任務 JSON 的 context.reviewFindings
    2. 讀取 context.testFiles 了解測試案例
    3. 篩選 severity === 'critical' 且 status === 'open' 的問題
    4. 依序修復每個問題
       - 使用 suggestion 和 example 作為實作參考
       - 確保測試通過
    5. 修復完每個 finding 後，更新其 status 為 'resolved'
    6. 更新任務 JSON 的 context.modifiedFiles

    ⚠️ 必須更新 finding status！修復後將對應 finding 的 status 改為 'resolved'。
    輸出格式請遵循 coder agent 的標準格式。
  "
)
```

### Step 7: coder 完成後

1. 更新 agents 陣列加入 coder 記錄
2. 更新 status 為 `review`
3. 呼叫 risk-reviewer（簡化審查，只驗證修復項目）

---

## 循環限制

- review-fix 迴圈最多 **2 輪**（reviewCycle ≤ 2）
- 超過 2 輪 → 強制停止，要求人工介入
- 如果同一個 finding 修復 2 次仍未通過 → 標記為需要人工介入

---

## 相關文件

- [review-fix-workflow.md](docs/review-fix-workflow.md) - 完整設計文檔
- [tester.md](.claude/agents/tester.md) - Tester Agent 定義
- [coder.md](.claude/agents/coder.md) - Coder Agent 定義
