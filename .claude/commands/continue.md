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

> **task_id 匹配**：支援完整 UUID 或 UUID 前綴（前 8 碼）匹配。

---

## Step 2: 階段轉移

參考：`shared/task-flow-diagrams.md`

| 當前 | 下一個 | 條件 |
|------|--------|------|
| requirement | specification/testing | 信心度達標 |
| specification | testing | 規格完成 |
| testing | development/gate | 測試生成 |
| development | review | 測試通過 + E2E 檢查 |
| review | gate | 審查完成 |
| gate | completed | GO 決策 |

### E2E 檢查（development → review）

- `e2e.required == false` → 直接 review
- `e2eMode == "auto"` → 需 passed
- `e2eMode == "manual"` → 允許（Conditional GO）
- 未設定 → 提示選擇

### Review Agent

| type | Reviewer |
|------|----------|
| feature | risk only |
| fix | risk only |
| refactor | style + risk |

---

## Step 2.4: 提取驗收指南（條件式）

當階段轉移為 `gate → completed` 且 `acceptance.testLayers.e2e.required == true` 時執行：

1. 從 gatekeeper 輸出提取 `═══ 人工驗收指南 ═══` 區塊
2. 讀取 spec 檔（`specs/{project}/{task_id}*.md`）的 Given-When-Then 場景描述
3. 搜尋相關 test suite（`tests/{project}/suites/*/scenarios/S*.yml`），讀取具體操作步驟
4. 組合成結構化驗收指南，存入 task JSON `acceptance.verificationGuide`

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
- from_stage = 當前階段
- to_stage = 目標階段
- agent_name = 下一階段的 Agent

> 此事件會統一處理：MCP 同步、Task JSON 更新、Kanban 移動、描述更新（進入 testing 時）。

---

## Step 3: 呼叫 Agent 並記錄 Metrics

參考：`shared/agent-call-patterns.md`

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
