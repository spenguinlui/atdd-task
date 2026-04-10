---
description: 部署 atdd-task 到遠端 Server（via AWS SSM）
---

# Deploy - 部署到 Server

> **使用時機**：將本地已 push 的 atdd-task 變更部署到遠端 EC2 Server。

## 設定

從 `.claude/config/aws-instances.yml` 讀取 `atdd_server` 的設定：

```yaml
INSTANCE_ID: instances.atdd_server[0].instance_id
APP_DIR: instances.atdd_server[0].app_dir
USER: instances.atdd_server[0].user
```

---

## Step 1: 選擇部署分支

使用 `AskUserQuestion` 詢問要部署的分支：

```
AskUserQuestion(
  questions: [{
    question: "要部署哪個分支？（直接按 Enter 使用預設 master）",
    header: "Deploy Branch",
    allowFreeText: true,
    defaultValue: "master"
  }]
)
```

將用戶輸入的值設為 `${BRANCH}`（空值或未輸入則使用 `master`）。

---

## Step 2: 確認本地狀態

```bash
# 檢查是否有未 push 的 commit（對比目標分支）
git log origin/${BRANCH}..${BRANCH} --oneline
```

**如果有未 push 的 commit**：

```markdown
┌──────────────────────────────────────────────────────┐
│ ⚠️ 有未 push 的 commit                               │
├──────────────────────────────────────────────────────┤
│                                                      │
│ {unpushed_commits}                                   │
│                                                      │
│ Server 會從 GitHub pull，需要先 push。               │
│ 是否先執行 git push？                                │
│                                                      │
└──────────────────────────────────────────────────────┘
```

使用 `AskUserQuestion` 確認是否自動 push。如果用戶同意，執行 `git push`。如果拒絕，中止部署。

**如果本地有未 commit 的變更**（git status 不乾淨），顯示提醒但不阻擋（可能只部署已 push 的部分）。

---

## Step 3: 部署 - Git Pull

```bash
COMMAND_ID=$(aws ssm send-command \
  --instance-ids "${INSTANCE_ID}" \
  --document-name "AWS-RunShellScript" \
  --parameters 'commands=["sudo -u ${USER} bash -c \"cd ${APP_DIR} && git pull origin ${BRANCH} 2>&1\""]' \
  --output text \
  --query "Command.CommandId")
```

等待完成並取得輸出。

**如果失敗**（merge conflict、網路問題等）→ 顯示錯誤訊息並中止。

---

## Step 4: 部署 - Docker Compose Rebuild

```bash
COMMAND_ID=$(aws ssm send-command \
  --instance-ids "${INSTANCE_ID}" \
  --document-name "AWS-RunShellScript" \
  --parameters 'commands=["sudo -u ${USER} bash -c \"cd ${APP_DIR}/infrastructure && docker compose up -d --build api worker 2>&1\""]' \
  --output text \
  --query "Command.CommandId")
```

等待完成並取得輸出（build 可能需要 30 秒以上，查詢結果時 sleep 適當等待）。

---

## Step 5: 健康檢查

```bash
COMMAND_ID=$(aws ssm send-command \
  --instance-ids "${INSTANCE_ID}" \
  --document-name "AWS-RunShellScript" \
  --parameters 'commands=["sudo -u ${USER} bash -c \"cd ${APP_DIR}/infrastructure && docker compose ps --format \\\"table {{.Name}}\t{{.Status}}\\\" 2>&1\""]' \
  --output text \
  --query "Command.CommandId")
```

確認 api 和 worker 容器都是 `Up` 狀態。

---

## Step 6: 輸出結果

### 成功

```markdown
┌──────────────────────────────────────────────────────┐
│ ✅ 部署完成                                          │
├──────────────────────────────────────────────────────┤
│                                                      │
│ 🖥️ Server：{INSTANCE_ID}                            │
│ 📂 路徑：{APP_DIR}                                   │
│ 🔀 Branch：{BRANCH}                                  │
│ 📥 Git：{git_pull_summary}                           │
│                                                      │
│ ═══ 容器狀態 ═══                                     │
│ ✅ api     — Up                                      │
│ ✅ worker  — Up                                      │
│                                                      │
│ 🌐 https://atdd.sunnyfounder.com                     │
│                                                      │
└──────────────────────────────────────────────────────┘
```

### 失敗

```markdown
┌──────────────────────────────────────────────────────┐
│ ❌ 部署失敗                                          │
├──────────────────────────────────────────────────────┤
│                                                      │
│ 失敗階段：{step_name}                                │
│ 錯誤訊息：{error_message}                            │
│                                                      │
│ 💡 建議：                                            │
│ • 檢查 server 上的 git 狀態                          │
│ • 檢查 Docker build log                              │
│                                                      │
└──────────────────────────────────────────────────────┘
```
