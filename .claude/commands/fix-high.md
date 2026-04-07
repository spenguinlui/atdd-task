---
description: 修復 Review 發現的 Critical + High 問題（TDD 流程）
---

# Fix High Priority Issues

修復 Review 階段發現的 Critical 和 High 嚴重度問題，使用 TDD 流程。

---

## 前置檢查

1. 確認有 active 任務
2. 確認任務狀態為 `review`
3. 確認 `context.reviewFindings` 存在
4. 確認有 severity 為 `critical` 或 `high` 的問題

---

## 執行步驟

### Step 1: 篩選問題

篩選 `severity === "critical"` 或 `severity === "high"` 的問題。

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
      "fixScope": "high"
    }
  },
  "history": [
    { "phase": "testing", "timestamp": "{ISO}", "reason": "fix-high" }
  ]
}
```

### Step 3: 更新 Kanban

執行 `shared/kanban-operations.md` 的「移動卡片」

### Step 4: 輸出訊息

```markdown
┌──────────────────────────────────────────────────────┐
│ 📋 修復 Critical + High 問題                         │
├──────────────────────────────────────────────────────┤
│ 📍 從：review                                        │
│ 📍 到：testing                                       │
│ 🔧 修復範圍：critical + high                         │
│                                                      │
│ 💡 可依序輸入：/clear → /continue 清理對話後繼續     │
│                                                      │
│ ═══ 待修復問題 ═══                                   │
│ 🔴 Critical:                                         │
│ 1. [SEC-001] 缺乏授權控制                            │
│ 2. [SEC-002] 併發控制不足                            │
│ 3. [SEC-003] 輸入驗證缺失                            │
│                                                      │
│ 🟠 High:                                             │
│ 4. [PERF-001] N+1 Query                              │
│ 5. [DATA-001] 缺乏 unique constraint                 │
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
    任務：補充測試案例以覆蓋 review 發現的 Critical 和 High 問題
    任務 JSON：{task_json_path}
    模式：fix-review

    請執行：
    1. 讀取任務 JSON 的 context.reviewFindings
    2. 篩選 severity 為 'critical' 或 'high' 且 status === 'open' 的問題
    3. 為每個問題生成測試案例
    4. 執行測試確認失敗
    5. 更新任務 JSON 的 context.testFiles

    輸出格式請遵循 tester agent 的標準格式。
  "
)
```

### Step 6: 後續流程

同 fix-critical.md，依序：
1. tester 補測試
2. coder 修復 — **必須將修復的 finding status 更新為 'resolved'**
3. 回到 review（risk-reviewer 比對既有 findings，只報告新問題）
4. gate

---

## 循環限制

- review-fix 迴圈最多 **2 輪**（reviewCycle ≤ 2）
- 超過 2 輪 → 強制停止，要求人工介入

---

## 相關文件

- [fix-critical.md](.claude/commands/fix-critical.md) - 只修復 Critical
- [review-fix-workflow.md](docs/review-fix-workflow.md) - 完整設計文檔
