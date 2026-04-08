# Agent 呼叫模式

## 標準呼叫格式

```
Task(
  subagent_type: "{agent_name}",
  prompt: "
    專案：{project}
    任務標題：{title}
    任務類型：{type}
    任務 ID：{uuid}

    {具體指令}
  "
)
```

> Agent 透過 `atdd_task_get(uuid)` 讀取任務資料，透過 `atdd_task_update(uuid, ...)` 更新任務。

## 各階段對應 Agent

| 階段 | Agent | 主要任務 |
|------|-------|----------|
| requirement | specist | Domain 識別、需求分析 |
| specification | specist | 規格撰寫、ATDD Profile |
| testing | tester | 測試生成、執行 |
| development | coder | 代碼實作、E2E 執行 |
| review | risk-reviewer（預設）+ style-reviewer（僅 refactor） | 平行審查 |
| gate | gatekeeper | 品質門檻、Go/No-Go |

## Metrics 記錄

Task tool 返回格式：`Done (21 tool uses · 41.9k tokens · 2m 12s)`

解析並透過 `atdd_task_add_metrics()` 記錄。

## 各階段可用命令（強制規範）

每個 Agent 返回結果後，**必須**在報告結尾列出當前階段的可用命令。

| 階段 | 可用命令 |
|------|---------|
| requirement / specification | `/continue {task_id}`, `/abort {task_id}` |
| testing | `/continue {task_id}`, `/e2e-manual`（僅 E2E required）, `/abort {task_id}` |
| development | `/continue {task_id}`, `/abort {task_id}` |
| review | `/continue {task_id}`, `/fix-critical`, `/fix-high`, `/fix-all`, `/abort {task_id}` |
| gate | `/done`, `/commit`, `/close`, `/abort {task_id}` |

**格式規範**（命令帶 task_id，讓使用者可在 `/clear` 後直接貼到新對話窗）：
```
🔗 Jira：{jira.url}
📌 下一步：
• /continue {task_id}     - 進入下一階段
• /abort {task_id}        - 放棄當前任務
```

Jira 連結：從 `jira.url` 取得。`jira.issueKey` 為 null 時省略 Jira 行。

### Review 階段完成後

必須逐條列出所有嚴重等級的項目（數量為 0 可省略整行，有數量的**必須列出內容**）。

## curator 呼叫入口

| 入口 | 觸發者 | prompt 差異 |
|------|--------|------------|
| `/knowledge` | 使用者 | 由 knowledge.md Step 3 直接呼叫 |
| `/test-knowledge` | tester | 附帶知識缺口 ID 和描述 |
| gate completed | gatekeeper | 附帶 knowledge discoveries |

共通：Curator 執行標準 5-phase 流程，差異僅在 prompt 背景資訊。
