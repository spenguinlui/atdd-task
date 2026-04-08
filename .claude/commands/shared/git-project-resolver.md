# Git 專案路徑解析（強制前置步驟）

> **所有涉及 Git 操作的命令（/done, /commit, /close）必須先執行此步驟。**
> **禁止在 atdd-hub 目錄執行任何專案的 git add / git commit。**

## 解析流程

### 1. 從任務 JSON 讀取

- `projectId`
- `git.branch`（如有）
- `context.modifiedFiles`（如有）

### 2. 查詢專案路徑

讀取 `.claude/config/projects.yml`，取得 `projects.{projectId}.path`。

如果檔案不存在或 `projects.{projectId}` 欄位不存在 → ERROR「專案配置不完整，請確認 .claude/config/projects.yml」。

### 3. 驗證規則

#### 規則 1：路徑不得為 atdd-hub

```
if PROJECT_PATH 包含 "atdd-hub" → ERROR，停止執行
```

> 例外：`stock_commentary` 等路徑本身在 atdd-hub 下的專案除外。

#### 規則 2：路徑必須存在且為 git repo

```bash
cd {PROJECT_PATH} && git rev-parse --is-inside-work-tree
```

失敗 → ERROR「專案路徑不存在或非 git repo」

#### 規則 3：分支必須匹配（如 git.branch 存在）

```bash
cd {PROJECT_PATH} && git branch --show-current
```

如果當前分支 != `git.branch` → 警告，AskUserQuestion 詢問是否切換分支。

#### 規則 4：modifiedFiles 應有對應變更

檢查 `context.modifiedFiles` 中的檔案在 `PROJECT_PATH` 下是否有 git diff。
如果沒有任何變更 → 警告「專案目錄無變更可 commit」（/close 可忽略此警告）。

## 解析結果

通過所有驗證後，輸出以下變數供後續步驟使用：

- **PROJECT_PATH** = `projects.yml` 中查到的絕對路徑
- **PROJECT_BRANCH** = MCP 任務資料（`atdd_task_get()` 回傳）中的 `metadata.git.branch`
- **TASK_MODIFIED_FILES** = MCP 任務資料中的 `metadata.context.modifiedFiles`

## 使用方式

後續所有 git 指令必須使用：

```bash
cd {PROJECT_PATH} && git add {files}
cd {PROJECT_PATH} && git commit -m "..."
cd {PROJECT_PATH} && git status
```

atdd-hub 的文件（requirements/specs/tasks）可另外 commit，但不是主要交付物。
