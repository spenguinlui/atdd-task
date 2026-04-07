# 任務狀態更新（事件驅動）

> 統一的狀態更新入口。所有命令透過觸發事件來更新任務狀態，由本模組統一處理所有副作用。
> 
> **MCP 為唯一資料來源**：所有狀態寫入透過 MCP tool 寫入 DB，不產生本地 JSON 檔案。

---

## Event 1: `stage-changed`

**觸發時機**：`/continue` 階段轉移時

**輸入**：
- task_id（UUID）
- from_stage（原階段）
- to_stage（目標階段）
- agent_name（下一階段的 Agent）

**副作用**：

### 1. MCP 同步

```
atdd_task_update(
  task_id: "{task_id}",
  status: "{to_stage}",
  phase: "{to_stage}",
  metadata: {
    "workflow": { "currentAgent": "{agent_name}" }
  }
)

atdd_task_add_history(
  task_id: "{task_id}",
  phase: "{to_stage}",
  status: "{to_stage}",
  note: "Stage changed: {from_stage} → {to_stage}"
)
```

### 2. 更新 Kanban

檢查任務 JSON 的 `jira.issueKey`：
- **不為 null** → `KANBAN_BACKEND=jira`
- **為 null** → `KANBAN_BACKEND=markdown`

```bash
bash .claude/scripts/kanban-adapter.sh move \
  --project {project} \
  --title "{description}" \
  --from {from_stage} \
  --to {to_stage}
```

### 3. 描述更新（條件式：進入 testing 且非 test 類型）

當 `to_stage == testing` 且任務 `type != test` 時，額外執行「更新描述」。

詳細步驟：

1. 從任務 JSON 取得 `id`（UUID 前 8 碼）和 `projectId`
2. 用 UUID 前綴 glob 找到相關檔案：
   - BA 報告：`requirements/{projectId}/{uuid前綴}*-ba.md`
   - Requirement：`requirements/{projectId}/{uuid前綴}*.md`（排除 `-ba.md`）
   - Spec：`specs/{projectId}/{uuid前綴}*.md`（fix 可能沒有 Spec）
3. 依優先序擷取業務描述（見下方格式相容規則）
4. 若有 Spec 檔案，從中擷取 `## Acceptance Criteria` 區塊
5. 組合成描述文字，寫入暫存檔 `/tmp/jira-desc-{uuid}.md`
6. 檢查任務 JSON 的 `jira.source`，決定寫入方式：

**`jira.source == "created"` 或 null**（我們建立的票）→ 更新 Description：
```bash
bash .claude/scripts/kanban-adapter.sh update \
  --project {project} \
  --title "{description}" \
  --description-file /tmp/jira-desc-{uuid}.md
```

**`jira.source == "linked"`**（既有票）→ 寫入 Comment，避免覆蓋 PM 原本的 Description：
```bash
bash .claude/scripts/kanban-adapter.sh update \
  --project {project} \
  --title "{description}" \
  --description-file /tmp/jira-desc-{uuid}.md \
  --as-comment
```

#### 格式相容規則（優先序）

依以下順序嘗試擷取業務描述，使用第一個成功匹配的來源：

**優先 1：標準 BA 報告**（`-ba.md` 檔案含 `## 需求摘要`）

直接擷取三個區塊：
- `## 需求摘要`
- `## 業務分析結論`
- `## 驗收條件`

**優先 2：Requirement 檔案含 `## BA` 區塊**

從 Requirement 檔的 `## BA` 區塊擷取內容，整區作為「業務分析結論」，並從 `## Request` 區塊擷取作為「需求摘要」。

**優先 3：僅有 `## Request` / `## SA`**（舊格式，僅相容用途）

從 `## Request` 擷取作為「需求摘要」，不產出「業務分析結論」和「驗收條件（BA）」區塊。

> Request 區塊可能包含技術術語，擷取時**必須轉譯為業務語言**：移除 backtick、將 snake_case 名稱和 Class 名稱替換為中文業務用語。

#### 組合格式

```
## 需求摘要
{擷取的需求摘要內容}

## 業務分析結論
{擷取的業務分析結論，僅優先 1/2 有此區塊}

## 驗收條件（BA）
{擷取的驗收條件，僅優先 1 有此區塊}

## Acceptance Criteria
- [ ] AC-1: ...
- [ ] AC-2: ...
```

空的區塊（無內容可擷取）應省略，不輸出空標題。

---

## Event 2: `task-completed`

**觸發時機**：`/done` 或 `/close` 結案時

**輸入**：
- task_id（UUID）
- commit_hash（optional，`/close` 可能沒有）
- metrics（optional，session 統計數據）

**副作用**：

### 1. MCP 同步

```
atdd_task_update(
  task_id: "{task_id}",
  status: "completed",
  metadata: {
    "context": { "completedAt": "{ISO timestamp}", "commit": "{commit_hash or null}", "closedWithoutCommit": {true if no commit_hash} },
    "metrics": {metrics if provided}
  }
)

atdd_task_add_history(
  task_id: "{task_id}",
  phase: "completed",
  status: "completed",
  note: "{結案方式描述}"
)
```

如有 metrics 的 agent 數據，逐個記錄：
```
atdd_task_add_metrics(
  task_id: "{task_id}",
  agent: "{agent_name}",
  tool_uses: {tools},
  tokens: {tokens}
)
```

### 2. 更新 Kanban

```bash
# 先取得 metrics
ruby .claude/scripts/session-stats.rb latest --format kanban > /tmp/kanban-metrics.txt

# 結案
bash .claude/scripts/kanban-adapter.sh complete \
  --project {project} \
  --title "{description}" \
  --commit {commit_hash} \
  --phase-history "{phase1} → {phase2} → ..." \
  --task-id {task_id_prefix} \
  --type {Feature/Fix/Refactor} \
  --domain {domain} \
  --branch {branch} \
  --metrics-file /tmp/kanban-metrics.txt
```

### 3. Epic 同步（條件式）

透過 `atdd_task_get(task_id)` 取得任務的 `metadata.epic` 字段：
- **有 epic 字段** → 執行 `shared/epic-sync-on-complete.md`
- **無 epic 字段** → 跳過

輸入：
- task_id（UUID）
- commit hash（來自輸入，或 "N/A"）

---

## Event 3: `task-cancelled`

**觸發時機**：`/abort` 放棄任務時

**輸入**：
- task_id（UUID）
- reason（放棄原因）

**副作用**：

### 1. MCP 同步

```
atdd_task_update(
  task_id: "{task_id}",
  status: "failed",
  metadata: {
    "context": { "failureReason": "{reason}", "abortedAt": "{當前階段}", "abortedBy": "user" }
  }
)

atdd_task_add_history(
  task_id: "{task_id}",
  phase: "failed",
  status: "failed",
  note: "Aborted: {reason}"
)
```

### 2. 更新 Kanban

```bash
bash .claude/scripts/kanban-adapter.sh fail \
  --project {project} \
  --title "{description}"
```

---

## Event 4: `task-deployed`

**觸發時機**：`/done --deploy` 啟用部署驗證時（取代直接 completed）

**輸入**：
- task_id（UUID）
- commit_hash
- metrics（optional）
- risk_level（low | medium | high，由 domain health 自動判斷）

**副作用**：

### 1. MCP 同步

```
atdd_task_update(
  task_id: "{task_id}",
  status: "deployed",
  metadata: {
    "context": { "commitHash": "{commit_hash}", "deployedAt": "{ISO timestamp}", "riskLevel": "{risk_level}", "verifyDeadline": "{deadline}" },
    "metrics": {metrics if provided}
  }
)

atdd_task_add_history(
  task_id: "{task_id}",
  phase: "deployed",
  status: "deployed",
  note: "Deployed with risk level: {risk_level}"
)
```

### 2. 更新 Kanban

```bash
bash .claude/scripts/kanban-adapter.sh move \
  --project {project} \
  --title "{description}" \
  --from gate \
  --to deployed
```

---

## Event 5: `task-verified`

**觸發時機**：`/verify` 確認 production 正常時

**輸入**：
- task_id（UUID）
- verified_by（user | auto | client）

**副作用**：

### 1. MCP 同步

```
atdd_task_update(
  task_id: "{task_id}",
  status: "verified",
  metadata: {
    "context": { "verifiedAt": "{ISO timestamp}", "verifiedBy": "{verified_by}" }
  }
)

atdd_task_add_history(
  task_id: "{task_id}",
  phase: "verified",
  status: "verified",
  note: "Verified by: {verified_by}"
)
```

### 2. 更新 Kanban

```bash
bash .claude/scripts/kanban-adapter.sh complete \
  --project {project} \
  --title "{description}" \
  --commit {commit_hash} \
  ...（同 task-completed 的 kanban 參數）
```

---

## Event 6: `task-escaped`

**觸發時機**：`/escape` 發現 production 問題時

**輸入**：
- task_id（UUID）
- escape_reason（問題描述）
- fix_task_id（若已建立 fix 票則填入）

**副作用**：

### 1. MCP 同步

```
atdd_task_update(
  task_id: "{task_id}",
  status: "escaped",
  metadata: {
    "context": { "escapedAt": "{ISO timestamp}", "escapeReason": "{escape_reason}", "fixTaskId": "{fix_task_id or null}" }
  }
)

atdd_task_add_history(
  task_id: "{task_id}",
  phase: "escaped",
  status: "escaped",
  note: "Escaped: {escape_reason}"
)
```

### 2. 更新 Kanban

```bash
bash .claude/scripts/kanban-adapter.sh fail \
  --project {project} \
  --title "{description}"
```

### 3. 建議建立 Fix 票

輸出提示：
```
⚠️ 任務 [{description}] 已標記為 escaped
建議執行：/fix {project}, {escape_reason}
新 fix 票的 causation.causedBy 將自動指向此任務
```
