# Git Branch 選擇流程

## Step 1: 取得當前狀態

```bash
cd {project_path} && git branch --show-current && git status --porcelain
```

## Step 2: 詢問分支選擇

使用 AskUserQuestion 詢問：

```
請選擇此任務的 Git Branch：

1. 直接在 master 開發
2. 建立新分支（輸入名稱）
```

**建議命名**：
- feature: `feature/{short-description}`
- fix: `fix/{short-description}`
- refactor: `refactor/{short-description}`

## Step 3: 處理選擇

| 選擇 | 動作 |
|------|------|
| 直接在 master | 確保在 master 分支 → 記錄 `git.branch = "master"` |
| 建立新分支 | `git checkout -b {name}` → 記錄 |

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
