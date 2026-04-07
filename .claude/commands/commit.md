---
description: 僅執行 Git Commit（不結案）
---

# Commit - 僅 Commit

> **使用時機**：想先 commit 變更，但任務還沒要正式結案。

## 前置檢查

### Step 1: 檢查是否有進行中的任務

呼叫 `atdd_task_list()` 取得所有任務，過濾出 active 任務（status 不是 `completed`、`aborted`、`verified`）。

從任務資料取得：
- `projectId` / `project`：專案 ID
- `description`：任務描述
- `type`：任務類型
- `domain`：Domain
- `context.modifiedFiles`：變更的檔案（從 metadata 取得）

**如果沒有 active 任務：**

```markdown
┌──────────────────────────────────────────────────────┐
│ ⚠️ 沒有進行中的任務                                  │
├──────────────────────────────────────────────────────┤
│                                                      │
│ /commit 需要有進行中的任務來生成 commit 訊息。       │
│                                                      │
│ 如果只是想執行一般的 git commit，請直接使用：        │
│ git add . && git commit -m "your message"           │
│                                                      │
└──────────────────────────────────────────────────────┘
```

---

## Step 1.5: 解析專案路徑（強制）

執行 `shared/git-project-resolver.md`，取得 PROJECT_PATH。

將後續所有步驟中的 `{project_path}` 替換為解析結果 PROJECT_PATH。

> **禁止在 atdd-hub 執行 git commit。**

---

## 執行 Commit

### Step 2: 檢查 Git 狀態

```bash
cd {project_path} && git status
cd {project_path} && git diff --staged
cd {project_path} && git diff
```

顯示變更摘要：

```markdown
┌──────────────────────────────────────────────────────┐
│ 📋 Git Commit 預覽                                   │
├──────────────────────────────────────────────────────┤
│                                                      │
│ 🏷️ 任務：[{projectId}] {description}                │
│ 📍 階段：{status}                                    │
│                                                      │
│ ═══ 變更檔案 ═══                                     │
│ 📁 已暫存：{staged_count} 個                         │
│ 📁 未暫存：{unstaged_count} 個                       │
│ 📁 未追蹤：{untracked_count} 個                      │
│                                                      │
│ ═══ Commit 訊息預覽 ═══                              │
│ {branch} {type}({domain}): {description}            │
│                                                      │
│ - {change_1}                                         │
│ - {change_2}                                         │
│                                                      │
│ Task: {task_id} (in progress)                       │
│                                                      │
│ Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com> │
│                                                      │
└──────────────────────────────────────────────────────┘
```

### Step 3: 確認執行

使用 `AskUserQuestion`：

```
AskUserQuestion(
  questions: [{
    question: "確認執行 Git Commit？",
    header: "Commit",
    options: [
      { label: "確認 Commit", description: "執行 git add + commit" },
      { label: "僅 Commit 已暫存", description: "只 commit 已 staged 的檔案" },
      { label: "取消", description: "不執行" }
    ],
    multiSelect: false
  }]
)
```

### Step 4: 執行 Git Commit

**選擇「確認 Commit」**：

```bash
# Add 相關檔案
cd {project_path} && git add {modified_files}

# Commit
cd {project_path} && git commit -m "$(cat <<'EOF'
{branch} {type}({domain}): {description}

- {change_1}
- {change_2}

Task: {task_id} (in progress)

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
EOF
)"
```

**選擇「僅 Commit 已暫存」**：

```bash
# 只 commit 已 staged 的
cd {project_path} && git commit -m "$(cat <<'EOF'
{branch} {type}({domain}): {description}

Task: {task_id} (in progress)

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
EOF
)"
```

### Step 5: 記錄 Commit（不移動任務）

取得 commit hash：

```bash
git rev-parse --short HEAD
```

透過 `atdd_task_update()` 更新任務（**不**改變 status）：

```json
{
  "context": {
    ...existing_context,
    "commits": [
      ...existing_commits,
      {
        "hash": "{commit_hash}",
        "message": "{commit_message_first_line}",
        "timestamp": "{ISO timestamp}",
        "phase": "{current_status}"
      }
    ]
  },
  "updatedAt": "{ISO timestamp}"
}
```

**MCP 同步**：`atdd_task_update(task_id, metadata={"context": {"commitHash": "{commit_hash}"}})`

> **注意**：任務可能有多次 commit（開發過程中），DB 的 metadata.context.commitHash 存最新的。

### Step 6: 輸出完成訊息

```markdown
┌──────────────────────────────────────────────────────┐
│ ✅ Commit 完成                                       │
├──────────────────────────────────────────────────────┤
│                                                      │
│ 📝 Commit：{commit_hash}                             │
│ 📝 訊息：{commit_message_first_line}                 │
│ 📁 檔案：{files_count} 個                            │
│                                                      │
│ ═══ 任務狀態 ═══                                     │
│ 📍 階段：{status}（未變更）                          │
│ 📋 任務仍在 active 中                                │
│                                                      │
│ 📝 下一步：                                          │
│ • /continue - 繼續任務流程                           │
│ • /done - 完整結案（如果已通過 gate）                │
│ • /close - 僅結案（不再 commit）                     │
│                                                      │
└──────────────────────────────────────────────────────┘
```

---

## 沒有變更可 Commit

如果 git status 顯示沒有變更：

```markdown
┌──────────────────────────────────────────────────────┐
│ ℹ️ 沒有變更可以 Commit                               │
├──────────────────────────────────────────────────────┤
│                                                      │
│ Working tree clean - 沒有待 commit 的變更。          │
│                                                      │
│ 📝 可用選項：                                        │
│ • /continue - 繼續任務流程                           │
│ • /close - 結案（更新任務狀態）                      │
│                                                      │
└──────────────────────────────────────────────────────┘
```

---

## Commit 訊息格式

### 標準格式

```
{branch} {type}({domain}): {description}

- {change_summary_1}
- {change_summary_2}

Task: {task_id} (in progress)

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
```

其中 `{branch}` 是任務的 `git.branch` 值（例如 `GRE-217`）。

### Type 對應

| 任務 type | Commit type |
|-----------|-------------|
| feature | feat |
| fix | fix |
| refactor | refactor |
| test | test |

### 範例

```
GRE-217 feat(Accounting::AccountsReceivable): 實作發票作廢功能

- 新增 VoidCurrentInvoice use case
- 新增授權控制檢查
- 新增 ERP 結算檢查

Task: abc12345 (in progress)

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
```
