---
description: 查看當前任務狀態和進度
---

# Task Status

## 資料搜集（一次完成）

### Step 1: MCP 任務查詢

呼叫 `atdd_task_list()` 取得所有任務。從結果中：
- **Active 任務**：status 不是 `completed`、`aborted`、`verified` 的
- 提取：id, type, description, status, project, domain, phase, metadata（含 workflow, epic 等）

**Active Epics**（仍讀本地 epic.yml，DB 未追蹤）：
```bash
for f in epics/*/*/epic.yml; do
  epic_status=$(grep '^status:' "$f" | awk '{print $2}')
  if [ "$epic_status" != "completed" ] && [ "$epic_status" != "aborted" ]; then
    echo "=== $f (status: $epic_status) ==="
    grep -E '^(title:|id:)' "$f"
    grep -c 'status: completed' "$f" | xargs -I{} echo "completed_tasks: {}"
    grep -c 'status: pending_spec' "$f" | xargs -I{} echo "pending_tasks: {}"
    grep -c 'status: developing' "$f" | xargs -I{} echo "developing_tasks: {}"
  fi
done
```

如果有 Active Epic，用 Read 工具讀取該 `epic.yml` 以取得 Phase 詳情（只讀 active 的）。

### Step 2: 最近完成的任務（僅在無 active task 時）

`atdd_task_list(status='completed', limit=3)` 取最近 3 筆。

---

## 輸出格式

### 文字概覽

按專案分組顯示 active 任務，每個任務一行，格式精簡：

```
📊 任務總覽

🎯 Epic: {title} ({project}) — {completed}/{total} ({percent}%)
   Phase 進行中: {current_phase_name}
   下一個可開始: {next_task_id}: {title}

📋 Active 任務 ({count})
┌─────────────────────────────────────────────────────────┐
│ {project}                                               │
│  {type} {desc}                                          │
│  階段: {status} → 下一步: /continue                     │
│                                                         │
│  {type} {desc}                                          │
│  階段: {status} | Agent: {agent}                        │
└─────────────────────────────────────────────────────────┘
```

**精簡原則**：
- 每個任務最多 2 行（標題 + 狀態）
- 不顯示 agents/metrics/history 等詳細資訊
- Epic 只顯示進度條和下一個任務
- 階段用簡短標籤：`requirement` `specification` `testing` `development` `review` `gate`

### 互動選單

文字概覽後，用 **AskUserQuestion** 提供可操作選項：

- 如果有可繼續的任務 → 列出每個任務作為選項（label 用 `{project}: {short_desc}`）
- 如果有 Epic 的下一個待開始任務 → 作為選項之一
- 始終包含「開始新任務」選項

選單範例：
```
question: "選擇要操作的任務？"
options:
  - label: "繼續: core_web ERP週期匯出修復"
    description: "目前在 review 階段，執行 /continue"
  - label: "開始: T2-3 上傳銀行回應推進ERP週期"
    description: "Epic 下一個可開始的任務"
  - label: "開始新任務"
    description: "使用 /feature、/fix、/refactor 開始新工作"
```

用戶選擇後：
- 「繼續」→ 自動執行 `/continue`
- 「開始 Epic 任務」→ 引導用戶使用對應的 `/feature` 或 `/fix` 命令
- 「開始新任務」→ 顯示可用命令列表

### 沒有 Active 任務時

顯示最近完成的 3 個任務，然後用 AskUserQuestion 提供：
- 各專案的 `/feature`、`/fix` 選項
- Epic 中下一個待開始的任務（如果有 active epic）
