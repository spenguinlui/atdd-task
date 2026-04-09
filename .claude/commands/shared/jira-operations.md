# Jira 操作

> Jira 整合操作，包含開票確認和描述更新。

## Jira 開票確認

使用 AskUserQuestion 詢問是否在 Jira 開票：

```
question: "是否在 Jira 開立任務票？"
header: "Jira"
options:
  - label: "否（僅本地追蹤）"
    description: "不建立 Jira Issue，僅透過 MCP 追蹤任務狀態"
  - label: "是（開立 Jira 票）"
    description: "在 Jira Cloud 建立 Issue 並同步任務狀態"
  - label: "已有 Jira 票（貼上連結）"
    description: "已在 Jira 建立 Issue，貼上連結即可關聯"
multiSelect: false
```

- 選「否」→ 跳過 Jira 開票，任務 JSON 的 `jira.issueKey` 和 `jira.url` 維持 null
- 選「是」→ 執行下方 create 命令，建立 Jira Issue 並回寫 issue key 到任務 JSON
- 選「已有 Jira 票」→ 使用 AskUserQuestion 請用戶貼上 Jira URL（例如 `https://sunnyfounder-it.atlassian.net/browse/GRE-217`），從 URL 解析 issue key（最後的 path segment，如 `GRE-217`），直接回寫 `jira.issueKey` 和 `jira.url` 到任務 JSON

## 建立 Jira Issue

選擇「是」時，呼叫 kanban-adapter.sh 建立 Jira Issue：

```bash
KANBAN_BACKEND=jira bash .claude/scripts/kanban-adapter.sh create \
  --project {project} \
  --title "{description}" \
  --column requirement \
  --tags "{domain}, {type}" \
  --priority {priority} \
  --workload {workload} \
  --background "{background}" \
  --scope "{scope}"
```

從輸出解析 issue key（格式 `✓ Jira issue created: {KEY} —`）。

## 更新 Jira 描述

進入 testing 階段時，將 BA 報告 + Acceptance Criteria 同步到 Jira：

**`jira.source == "created"` 或 null**（我們建立的票）→ 更新 Description：
```bash
KANBAN_BACKEND=jira bash .claude/scripts/kanban-adapter.sh update \
  --project {project} \
  --title "{description}" \
  --description-file /tmp/jira-desc-{uuid}.md
```

**`jira.source == "linked"`**（既有票）→ 寫入 Comment，避免覆蓋 PM 原本的 Description：
```bash
KANBAN_BACKEND=jira bash .claude/scripts/kanban-adapter.sh update \
  --project {project} \
  --title "{description}" \
  --description-file /tmp/jira-desc-{uuid}.md \
  --as-comment
```
