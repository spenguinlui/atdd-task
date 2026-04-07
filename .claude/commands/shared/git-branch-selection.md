# Git Branch 選擇流程

## Step 1: 取得當前狀態

```bash
cd {project_path} && git branch --show-current && git status --porcelain
```

## Step 2: 顯示選項

### 有 Jira Ticket 時（從 Jira 確認步驟取得 issue key）

如果已有 Jira issue key（例如 `GRE-217`，來自新建或貼上的 Jira 票），**自動以 issue key 作為分支名稱**：

- 如果分支 `{issue_key}` 已存在 → `git checkout {issue_key}`
- 如果分支不存在 → `git checkout -b {issue_key}`
- 記錄 `git.branch = "{issue_key}"`

不需要詢問用戶，直接建立/切換。

### 無 Jira Ticket 時

使用 AskUserQuestion 詢問：

```
請選擇此任務的 Git Branch：

選項：
1. 使用當前分支：{current_branch}
2. 建立新分支（輸入名稱）
3. 切換到既有分支（輸入名稱）
```

**建議命名**：
- feature: `feature/{short-description}`
- fix: `fix/{short-description}`
- refactor: `refactor/{short-description}`

## Step 3: 處理選擇

| 選擇 | 動作 |
|------|------|
| 使用當前分支 | 記錄 `git.branch = "{current_branch}"` |
| 建立新分支 | `git checkout -b {name}` → 記錄 |
| 切換到既有 | `git checkout {name}` → 記錄 |

## Step 4: 未提交變更處理

如果工作目錄有未提交變更：

```
⚠️ 工作目錄有未提交的變更：
{變更列表}

請先處理這些變更（commit 或 stash）後再啟動任務。
```

**停止執行，不建立任務 JSON。**

## Step 5: 記錄到 JSON

```json
{
  "git": {
    "branch": "{selected_branch}"
  }
}
```
