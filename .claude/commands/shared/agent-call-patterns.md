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

## specist 呼叫

```
請執行以下步驟：
1. Domain 識別：讀取 domains/{project}/domain-registry.md
2. 讀取 Domain 知識（ul.md, business-rules.md）
3. 分析需求並評估信心度
4. 如果信心度 < 95%，列出需要澄清的問題
5. 選擇 ATDD Profile
6. 撰寫 Given-When-Then 規格

完成後更新任務 JSON 的 domain 和 context.relatedDomains 欄位。
```

## tester 呼叫

```
請執行以下步驟：
1. 讀取任務 JSON 的 acceptance profile
2. 讀取規格檔案
3. 根據 profile 生成驗收測試
4. 執行測試（預期失敗）
5. 如果 E2E required，提供選擇

輸出格式遵循 tester agent 標準。
```

## coder 呼叫

```
請執行以下步驟：
1. 讀取失敗的測試
2. 讀取規格和 style guide
3. 實作最小代碼讓測試通過
4. 如果 e2eMode == "auto"，執行 E2E

完成後更新 context.modifiedFiles。
```

## Metrics 記錄

Task tool 返回格式：
```
Done (21 tool uses · 41.9k tokens · 2m 12s)
```

解析並更新 JSON：
```json
{
  "agents": [
    {
      "name": "{agent}",
      "metrics": {
        "toolUses": 21,
        "tokens": 41900,
        "duration": "2m 12s"
      }
    }
  ]
}
```

## 各階段可用命令參考表

每個 Agent 返回結果後，**必須**在報告結尾列出當前階段的可用命令，讓用戶清楚知道所有選項。

| 階段 | 可用命令 | 說明 |
|------|---------|------|
| requirement | `/continue {task_id}` | 進入下一階段（specification 或 testing） |
| | `/status` | 查看當前任務進度 |
| | `/abort` | 放棄當前任務 |
| specification | `/continue {task_id}` | 進入 testing 階段 |
| | `/status` | 查看當前任務進度 |
| | `/abort` | 放棄當前任務 |
| testing | `/continue {task_id}` | 進入 development 階段（自動化 E2E） |
| | `/e2e-manual` | 標記使用人工 E2E 驗證（僅 E2E required 時） |
| | `/status` | 查看當前任務進度 |
| | `/abort` | 放棄當前任務 |
| development | `/continue {task_id}` | 進入 review 階段 |
| | `/status` | 查看當前任務進度 |
| | `/abort` | 放棄當前任務 |
| review | `/continue {task_id}` | 進入 gate 階段 |
| | `/fix-critical` | 修復 Critical 問題（TDD 流程） |
| | `/fix-high` | 修復 Critical + High 問題（TDD 流程） |
| | `/fix-all` | 修復所有問題（TDD 流程） |
| | `/status` | 查看當前任務進度 |
| | `/abort` | 放棄當前任務 |
| gate | `/done` | Commit + 結案（最常用） |
| | `/commit` | 僅 Commit |
| | `/close` | 僅結案 |
| | `/status` | 查看當前任務進度 |
| | `/abort` | 放棄當前任務 |

**格式規範**：Agent 報告結尾使用以下格式（命令必須帶 task_id，讓使用者可在 `/clear` 後直接貼到新對話窗）：
```
🔗 Jira：{jira.url}
📌 下一步：
• /continue {task_id}     - 進入下一階段
• /abort {task_id}        - 放棄當前任務
```

**Jira 連結規則**：從任務 JSON 的 `jira.url` 取得。若 `jira.issueKey` 為 null（test 任務或 markdown backend），則省略 `🔗 Jira` 行。

## Epic specist 呼叫（Requirement 階段）

```
Task(
  subagent_type: "specist",
  prompt: "
    專案：{project}
    Epic 標題：{title}
    Epic ID：{epic-id}
    模式：Epic Requirement

    請執行 Epic Requirement 模式（見 specist agent 定義的「Epic 模式」區塊）。

    執行步驟：
    1. Domain 識別：讀取 domains/{project}/domain-map.md
    2. 讀取 Domain 知識（ul.md, business-rules.md, strategic/, tactical/）
    3. 分析需求並評估信心度（≥ 95%）
    4. 如果信心度 < 95%，列出需要澄清的問題
    5. 產出 Epic Requirement + BA 報告

    產出路徑：
    - Requirement：requirements/{project}/{epic-id}-{short_name}.md
    - BA 報告：requirements/{project}/{epic-id}-{short_name}-ba.md

    Epic 特有指引：
    - SA 區塊涵蓋整個 Epic 的整體分析
    - BA 驗收條件為 Epic 層級（完成後商務上要看到什麼）
    - 不需要 ATDD Profile 選擇
    - 不需要 Given-When-Then 規格
    - 不需要更新任務 JSON
  "
)
```

## Epic specist 呼叫（Decomposition 階段）

```
Task(
  subagent_type: "specist",
  prompt: "
    專案：{project}
    Epic 標題：{title}
    Epic ID：{epic-id}
    模式：Epic Decomposition

    請執行 Epic Decomposition 模式（見 specist agent 定義的「Epic 模式」區塊）。

    已確認的需求文件（直接讀取，不要重新分析需求）：
    - Requirement：requirements/{project}/{epic-id}-{short_name}.md
    - BA 報告：requirements/{project}/{epic-id}-{short_name}-ba.md

    執行步驟：
    1. 讀取已確認的 Requirement + BA
    2. Phase 拆分（調查/清理/核心/驗證）
    3. 子任務識別（T{phase}-{seq} 編號、依賴關係、類型標註）
    4. 輸出 Epic 提案（格式見 epic.md）

    ⛔ 禁止：設計 code 結構、class 名稱、檔案命名、技術實作方式、程式碼片段。
    子任務標題只描述業務目的，不描述技術手段。
    這是提案階段，不要建立任何檔案。
  "
)
```

---

## curator 呼叫

**觸發來源 1：/knowledge（使用者主動）**
```
由 knowledge.md 直接呼叫，見 knowledge.md Step 3。
```

**觸發來源 2：/test-knowledge（測試發現知識缺口）**
```
專案：{project}
Domain(s)：{domain}
模式：single_domain
觸發來源：test-knowledge
知識缺口：{kg_id} — {description}
```

**觸發來源 3：/feature gate（Gatekeeper 識別新知識）**
```
專案：{project}
Domain(s)：{task.domain}
模式：single_domain
觸發來源：feature-gate
知識發現：{gate report 中的 discoveries}
```

**共通規範**：Curator 執行標準 5-phase 流程。
所有 3 個入口都使用相同的 Curator Agent，差異僅在 prompt 背景資訊。
