---
description: 確認進入下一個任務階段
---

# Continue Task

## Step 1: 檢查 Active 任務

呼叫 `atdd_task_list()` 取得所有任務，過濾出 status 不是 `completed`、`aborted`、`verified` 的為 active 任務。收集：id, project, description, status, type。

| 情況 | 處理 |
|------|------|
| 沒有任務 | 提示啟動任務 |
| 1 個任務 | 直接繼續 |
| 多個任務 | AskUserQuestion 選擇 |

支援：`/continue {task_id}` 或 `/continue {project}`

> **task_id 匹配**：必須使用完整 UUID。

---

## Step 1.5: 產出審閱驗證（強制門檻）

> ⛔ **必須在轉移前驗證上一階段的產出是否已在對話窗完整呈現。**
> 如果用戶是在新對話中執行 `/continue`（透過任務 JSON 恢復），此檢查跳過。

### 驗證規則

| 當前 status | 必須在對話中已呈現 | 缺少時處理 |
|-------------|-------------------|-----------|
| requirement | ① 信心度逐維度明細 ② SA 分析摘要 ③ BA 報告完整內容 ④ 驗收項目清單 | 讀取 requirement + BA 檔案，在對話窗補充呈現後再轉移 |
| specification | ① 所有 Spec 場景的完整 Given-When-Then ② ATDD Profile 選擇理由 | 讀取 spec 檔案，在對話窗補充呈現後再轉移 |
| testing | ① 完整測試案例清單（逐案 Given-When-Then） ② 測試執行結果（逐案列出） | 讀取測試檔案，在對話窗補充呈現後再轉移 |
| development | 不需額外驗證（coder 產出即程式碼） | — |
| review | 不需額外驗證（review 結果已有嚴格輸出規範） | — |

### 補充呈現格式

當需要補充時，先輸出：
```
📖 補充呈現上一階段產出（供審閱）：
---
{完整內容}
---
確認無誤後請再次 /continue
```

然後**停止**，等待用戶確認後再次 `/continue` 才執行轉移。

---

## Step 2: 階段轉移（決定 next_stage 和 next_agent）

> **重要**：此步驟的產出是 `next_stage` 和 `next_agent` 兩個變數。
> 後續 Step 2.1 和 Step 3 **必須使用這兩個變數**，禁止從任務 JSON 的 `currentAgent` 決定呼叫對象。

參考：`shared/task-flow-diagrams.md`

### 轉移表

| 當前 status | next_stage | next_agent | 條件 |
|-------------|------------|------------|------|
| requirement | specification | specist | Feature：信心度達標 |
| requirement | testing | tester | Fix：信心度達標（跳過 spec） |
| specification | testing | tester | 規格完成 |
| testing | development | coder | 測試生成 |
| testing | gate | gatekeeper | 僅 test 類型任務（無 dev） |
| development | review | risk-reviewer | 測試通過 + E2E 檢查（見下方） |
| review | gate | gatekeeper | 審查完成 |
| gate | completed | — | GO 決策（由 /done 處理，非 /continue） |

### E2E 檢查（development → review）

- `e2e.required == false` → 直接 review
- `e2eMode == "auto"` → 需 passed
- `e2eMode == "manual"` → 允許（Conditional GO）
- 未設定 → 提示選擇

### Review Agent

`next_agent` 為 risk-reviewer，但依任務類型決定是否加 style-reviewer：

| type | Reviewer |
|------|----------|
| feature | risk only |
| fix | risk only |
| refactor | style + risk（平行呼叫） |

---

## Step 2.4: 提取驗收指南（條件式）

當階段轉移為 `gate → completed` 且 `acceptance.testLayers.e2e.required == true` 時執行：

1. 從 gatekeeper 輸出提取 `═══ 人工驗收指南 ═══` 區塊
2. 從 MCP 讀取 spec 內容（`atdd_task_get(task_id)` → `metadata.spec`）的 Given-When-Then 場景描述
3. 搜尋相關 test suite（`tests/{project}/suites/*/scenarios/S*.yml`），讀取具體操作步驟
4. 組合成結構化驗收指南，透過 `atdd_task_update()` 存入 MCP 的 `acceptance.verificationGuide`

**儲存內容格式**：

```markdown
📋 驗收場景：
1. [ ] {場景1 Given-When-Then 摘要}
2. [ ] {場景2 Given-When-Then 摘要}

📹 E2E 測試套件：{suite-id}（如有）
   執行方式：/test-run {project}, {suite-id}

🔍 驗收步驟：
  {場景1}:
    1. {具體操作步驟 from scenario YAML}
    2. {具體操作步驟}
    預期：{expectedResult}
```

> 如果沒有 spec 檔或 test suite，僅保留 gatekeeper 輸出的驗收指南區塊。

---

## Step 2.1: 狀態更新

執行 `shared/task-state-update.md` 的 **`stage-changed`** 事件：

- task_id = 任務 UUID
- from_stage = 當前 status（從 Step 1 讀取）
- to_stage = **`next_stage`**（從 Step 2 轉移表決定）
- agent_name = **`next_agent`**（從 Step 2 轉移表決定）

> 此事件會統一處理：MCP 狀態更新、Jira 描述更新（進入 testing 時）。

---

## Step 3: 呼叫 next_agent 並記錄 Metrics

> **禁止**從任務 JSON 的 `metadata.workflow.currentAgent` 決定呼叫對象。
> **必須**使用 Step 2 轉移表產出的 `next_agent`。

參考：`shared/agent-call-patterns.md`，以 `next_agent` 作為 `subagent_type`。

**Agent 完成後的輸出格式**（必須嚴格遵守，所有命令帶 task_id）：
```
📌 下一步：
• /continue {task_id}     - 進入下一階段
• /abort {task_id}        - 放棄當前任務
```

> 其他命令（/status、/fix-*、/done 等）不需要列出，用戶已知。只列主要動作。

### Review 階段完成後的輸出規範

Review 結果必須列出**所有嚴重等級的所有項目**，不得省略任何等級：

```
Review 完成

Style Review: Grade {grade} ({score}/100)  ← 僅 refactor 時顯示
- Critical: {N}
  - {id}: {description}
- High: {N}
  - {id}: {description}
- Major: {N}
  - {id}: {description}
- Suggestion: {N}（非必要）
  - {id}: {description}

Risk Review: {risk_level}
- Critical: {N}
  - {id}: {description}
- High: {N}
  - {id}: {description}
- Medium: {N}
  - {id}: {description}
- Low: {N}
  - {id}: {description}

📌 下一步：
• /continue {task_id}     - 進入 gate 階段
• /fix-critical {task_id} - 修復 Critical 問題
• /fix-high {task_id}     - 修復 Critical + High
• /fix-all {task_id}      - 修復所有問題
• /abort {task_id}        - 放棄當前任務
```

> 數量為 0 的等級可省略整行。但有數量的等級**必須逐條列出**，禁止只寫數量不列內容。
