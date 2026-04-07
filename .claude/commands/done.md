---
description: 完整結案（Commit + 更新任務狀態）
---

# Done - 完整結案

> **使用時機**：Gatekeeper GO 決策後

## Step 1: 前置檢查

呼叫 `atdd_task_list(status='gate')` 取得所有 gate 階段的任務，檢查是否有 GO 決策。

沒有可結案任務 → 提示使用 `/status`
多個 GO 任務 → AskUserQuestion 選擇

---

## Step 2: 確認執行

AskUserQuestion 確認：Commit + 更新狀態 + 更新 Kanban

---

## Step 3: 收集 Session 統計

**取得統計數據**：

```bash
# 使用 "latest" 自動找最新的 session
ruby .claude/scripts/session-stats.rb latest --format kanban

# 或指定特定 session ID
ruby .claude/scripts/session-stats.rb {session_id} --task {task_id_prefix} --format kanban
```

**輸出格式**：
```
**Agents**: specist(14/2.1k), tester(8/1.4k), coder(31/2.5k), gatekeeper(38/10.3k)
**總計**: 114 tools / 18.2M tokens / 2h 30m
```

---

## Step 3.5: 解析專案路徑（強制）

執行 `shared/git-project-resolver.md`，取得 PROJECT_PATH。

後續所有 git 指令必須使用：
```bash
cd {PROJECT_PATH} && git add ...
cd {PROJECT_PATH} && git commit ...
```

> **禁止在 atdd-hub 執行 git commit。** atdd-hub 的文件（requirements/specs）可另外 commit，但不是主要交付。

---

## Step 4: Git Commit

**Commit 訊息格式**：
```
{branch} {type}({domain}): {description}

- {changes}

Task: {task_id}
Metrics: {total_tools} tools / {total_tokens} tokens / {duration}
```

其中 `{branch}` 是任務 JSON 的 `git.branch` 值（例如 `GRE-217`）。

記錄 commit hash

---

## Step 5: 更新任務狀態

執行 `shared/task-state-update.md` 的 **`task-completed`** 事件：

- commit_hash = Step 4 的 commit hash
- metrics = Step 3 的統計數據

> 此事件會統一處理：Task JSON 更新、檔案移動、Kanban 結案、Epic 同步（如有）。

---

## Step 6: 輸出完成訊息

任務識別、Commit、狀態、Metrics

如果 `acceptance.verificationGuide` 存在，在知識更新與 Epic 同步之前加入：

```markdown
│ ═══ 人工驗收 ═══                                     │
│ {verificationGuide 內容}                              │
```

接續：知識更新提案（如有）、Epic 同步（如有）

---

## 錯誤處理

Commit 失敗 → 提示 `/commit` 重試或 `/close` 僅結案
