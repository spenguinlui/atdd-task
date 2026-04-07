---
description: 僅結案（更新任務狀態，不執行 Git Commit）
---

# Close - 僅結案

> **使用時機**：已經手動 commit 過，或不需要 commit，只想更新任務狀態為完成。

## 前置檢查

### Step 1: 檢查是否有可結案的任務

呼叫 `atdd_task_list(status='gate')` 取得所有 gate 階段的任務。

讀取任務資料，檢查：
- `status` 是否為 `gate`
- 是否有 gatekeeper 的 GO 決策記錄

**如果沒有符合條件的任務：**

```markdown
┌──────────────────────────────────────────────────────┐
│ ⚠️ 沒有可以結案的任務                                │
├──────────────────────────────────────────────────────┤
│                                                      │
│ /close 只能在 Gatekeeper 給出 GO 決策後使用。        │
│                                                      │
│ 請確認：                                             │
│ • 任務是否已通過 gate 階段？                         │
│ • Gatekeeper 是否已給出 GO 決策？                    │
│                                                      │
│ 📝 使用 /status 查看當前任務狀態                     │
│                                                      │
└──────────────────────────────────────────────────────┘
```

---

## 執行結案

### Step 2: 顯示結案預覽

```markdown
┌──────────────────────────────────────────────────────┐
│ 📋 結案確認（僅更新狀態）                            │
├──────────────────────────────────────────────────────┤
│                                                      │
│ 🏷️ 任務：[{projectId}] {description}                │
│ 🎯 決策：GO                                          │
│                                                      │
│ ═══ 即將執行 ═══                                     │
│                                                      │
│ 1. 更新任務狀態                                      │
│    • 狀態：gate → completed                          │
│    • 移動：active/{id}.json → completed/{id}.json   │
│                                                      │
│ 2. 更新 Kanban                                       │
│    • 移動卡片至 Completed 欄                         │
│    • 加入 Metrics 摘要                               │
│                                                      │
│ ⚠️ 不會執行 Git Commit                               │
│                                                      │
│ 確認執行？(y/n)                                      │
└──────────────────────────────────────────────────────┘
```

### Step 2.5: 解析專案路徑（強制）

執行 `shared/git-project-resolver.md`，取得 PROJECT_PATH。

將後續所有步驟中的 `{project_path}` 替換為解析結果 PROJECT_PATH。

> **禁止在 atdd-hub 執行 git 操作。**

---

### Step 3: 檢查未 Commit 的變更

```bash
cd {project_path} && git status
```

如果有未 commit 的變更，顯示警告：

```markdown
┌──────────────────────────────────────────────────────┐
│ ⚠️ 注意：有未 Commit 的變更                          │
├──────────────────────────────────────────────────────┤
│                                                      │
│ 📁 未暫存：{unstaged_count} 個                       │
│ 📁 未追蹤：{untracked_count} 個                      │
│                                                      │
│ 如果繼續結案，這些變更不會被記錄在 commit 中。       │
│                                                      │
│ 請選擇：                                             │
│ • 繼續結案 - 忽略未 commit 的變更                    │
│ • 先 Commit - 使用 /done 執行完整結案                │
│ • 取消 - 不執行                                      │
│                                                      │
└──────────────────────────────────────────────────────┘
```

使用 `AskUserQuestion`：

```
AskUserQuestion(
  questions: [{
    question: "有未 commit 的變更，要如何處理？",
    header: "變更處理",
    options: [
      { label: "繼續結案", description: "忽略未 commit 的變更，僅更新任務狀態" },
      { label: "先 Commit", description: "改用 /done 執行完整結案" },
      { label: "取消", description: "不執行任何操作" }
    ],
    multiSelect: false
  }]
)
```

如果選擇「先 Commit」，提示用戶使用 `/done`。

---

### Step 4: 更新任務狀態

執行 `shared/task-state-update.md` 的 **`task-completed`** 事件：

- commit_hash = 從 context.commit 讀取，或 null
- metrics = null（close 不收集新 metrics）

> 此事件會統一處理：Task JSON 更新、檔案移動、Kanban 結案、Epic 同步（如有）。

---

### Step 5: 輸出完成訊息

```markdown
┌──────────────────────────────────────────────────────┐
│ 🎉 任務結案完成（僅狀態更新）                        │
├──────────────────────────────────────────────────────┤
│                                                      │
│ 🏷️ 任務：[{projectId}] {description}                │
│                                                      │
│ ═══ 任務狀態 ═══                                     │
│ ✅ 狀態：completed                                   │
│ 📁 記錄：已保存至 DB                                 │
│ 📋 Kanban：已更新                                    │
│                                                      │
│ ═══ Git ═══                                          │
│ ⚠️ 未執行新的 commit                                 │
│ 📝 最近 commit：{last_commit_hash 或 "無"}          │
│                                                      │
│ ═══ Metrics 摘要 ═══                                 │
│ Agents: {agents_summary}                             │
│ 總計: {totalToolUses} tools / {totalTokens}k / {dur}│
│                                                      │
│ ═══ 人工驗收（如 verificationGuide 存在）═══          │
│ {verificationGuide 內容}                              │
│                                                      │
│ ═══ Epic 同步（如有）═══                             │
│ 📦 Epic：{epic.id}                                   │
│ ✅ 任務：{epic.taskId} 已標記完成                    │
│ 📊 進度：{completed}/{total} ({progress}%)           │
│                                                      │
└──────────────────────────────────────────────────────┘
```

---

## 錯誤處理

### 任務不在 gate 階段

```markdown
┌──────────────────────────────────────────────────────┐
│ ⚠️ 任務尚未通過審查                                  │
├──────────────────────────────────────────────────────┤
│                                                      │
│ 📍 當前階段：{status}                                │
│                                                      │
│ 任務需要先通過 gate 階段才能結案。                   │
│                                                      │
│ 📝 請使用 /continue 繼續任務流程                     │
│                                                      │
└──────────────────────────────────────────────────────┘
```

### Gatekeeper 決策為 NO-GO

```markdown
┌──────────────────────────────────────────────────────┐
│ ⚠️ 任務未通過品質門檻                                │
├──────────────────────────────────────────────────────┤
│                                                      │
│ 🎯 Gatekeeper 決策：NO-GO                            │
│                                                      │
│ 請先修復以下問題：                                   │
│ {列出 NO-GO 原因}                                    │
│                                                      │
│ 📝 修復後使用 /continue 重新檢查                     │
│                                                      │
└──────────────────────────────────────────────────────┘
```

---

## 多個任務選擇

如果有多個任務都可以結案，使用 `AskUserQuestion`：

```
AskUserQuestion(
  questions: [{
    question: "有多個任務可以結案，請選擇：",
    header: "選擇任務",
    options: [
      { label: "[sf_project] 專案審核流程", description: "gate - GO" },
      { label: "[core_web] 登入修復", description: "gate - GO" }
    ],
    multiSelect: false
  }]
)
```
