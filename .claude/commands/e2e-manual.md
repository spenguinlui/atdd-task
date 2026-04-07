---
description: 標記任務使用人工 E2E 驗證（跳過自動化 E2E 測試）
---

# E2E Manual - 人工 E2E 驗證

## 用途

當任務需要 E2E 驗收測試，但不適合使用自動化測試時，使用此命令標記為人工驗證。

**適用場景**：
- 複雜的用戶互動流程（拖放、手勢）
- 需要人工判斷的視覺驗證
- 外部系統整合（第三方 API、OAuth）
- 列印/下載功能驗證
- 跨瀏覽器/跨裝置測試

## 執行流程

### Step 1：找到當前任務

呼叫 `atdd_task_list()` 取得所有任務，過濾出 active 任務。

找到當前進行中的任務（通常是最近操作的）。如果有多個任務，詢問用戶要選擇哪個。

### Step 2：檢查任務狀態

```
驗證條件：
- status 必須是 "testing" 或 "development"
- acceptance.testLayers.e2e.required 必須是 true

如果不符合：
- 如果 e2e.required == false → 提示「此任務不需要 E2E 測試」
- 如果 status 不在 testing/development → 提示「只能在 testing 或 development 階段使用」
```

### Step 3：更新任務狀態

呼叫 `atdd_task_update(task_id, metadata={"acceptance": {"e2eMode": "manual", "results": {"e2e": {"status": "manual_pending"}}}})` 更新任務。

### Step 4：繼續流程

根據當前階段決定下一步：

| 當前階段 | 下一步 |
|----------|--------|
| testing | 進入 development（呼叫 coder）|
| development | 進入 review（Unit Tests 須已通過）|

---

## 輸出格式

### 成功標記

```markdown
┌──────────────────────────────────────────────────────┐
│ 📋 E2E 測試模式設定                                  │
├──────────────────────────────────────────────────────┤
│ 📍 任務：[{projectId}] {description}                 │
│ 📍 模式：人工驗證（manual）                          │
│                                                      │
│ ✅ 已標記為人工 E2E 驗證                             │
│                                                      │
│ 📝 說明：                                            │
│ • Unit Tests 仍會自動執行                            │
│ • E2E 測試將跳過自動化執行                           │
│ • Gatekeeper 會提供人工驗收清單                      │
│ • 最終決策會是 Conditional GO                        │
│                                                      │
│ 正在繼續到 {next_phase}...                           │
└──────────────────────────────────────────────────────┘
```

### 錯誤：不需要 E2E

```markdown
┌──────────────────────────────────────────────────────┐
│ ⚠️ 此任務不需要 E2E 測試                             │
├──────────────────────────────────────────────────────┤
│                                                      │
│ 任務的 acceptance profile 未要求 E2E 測試。          │
│                                                      │
│ 當前設定：                                           │
│ • profile: {profile}                                 │
│ • e2e.required: false                                │
│                                                      │
│ 請直接使用 /continue 繼續。                          │
│                                                      │
└──────────────────────────────────────────────────────┘
```

### 錯誤：階段不正確

```markdown
┌──────────────────────────────────────────────────────┐
│ ⚠️ 無法在此階段設定 E2E 模式                         │
├──────────────────────────────────────────────────────┤
│                                                      │
│ /e2e-manual 只能在 testing 或 development 階段使用。 │
│                                                      │
│ 當前階段：{status}                                   │
│                                                      │
│ 💡 建議：                                            │
│ • 如果在 review 階段，E2E 模式已鎖定                 │
│ • 如果需要變更，請 /abort 重新開始任務               │
│                                                      │
└──────────────────────────────────────────────────────┘
```

---

## 與 /continue 的差異

| 命令 | E2E 處理 | 適用場景 |
|------|----------|----------|
| `/continue` | 執行自動化 E2E（e2eMode = "auto"）| 標準 CRUD、表單、列表頁 |
| `/e2e-manual` | 跳過自動化 E2E（e2eMode = "manual"）| 複雜互動、視覺驗證 |

---

## 人工驗收流程

使用 `/e2e-manual` 後，任務流程：

```
testing → development → review → gate
                                  ↓
                         Conditional GO
                                  ↓
                         人工在瀏覽器驗收
                                  ↓
                            完成任務
```

**Gatekeeper 會提供**：
1. 人工驗收清單（來自 fixture 或 spec）
2. 驗證步驟（登入、操作、預期結果）
3. 環境準備指令（setup script）
4. 清理指令（cleanup script）
