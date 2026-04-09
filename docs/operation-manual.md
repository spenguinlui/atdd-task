# ATDD Hub 操作手冊

本手冊說明如何使用 ATDD Hub 的 Command-Driven 工作流程進行專案任務開發。

---

## 目錄

1. [快速開始](#快速開始)
2. [任務類型](#任務類型)
3. [Epic 管理](#epic-管理)
4. [工作流程詳解](#工作流程詳解)
5. [6 Agent 架構](#6-agent-架構)
6. [Commands 參考](#commands-參考)
7. [Metrics 追蹤](#metrics-追蹤)
8. [常見問題](#常見問題)

---

## 快速開始

### 啟動新任務

使用 Slash Command 啟動任務：

```
/feature sf_project, 專案審核流程
```

系統會自動：
1. 建立任務記錄（JSON + MCP）
2. 進入 `requirement` 階段
3. 呼叫 `specist` Agent 開始需求分析
4. 詢問你的需求細節

### 與 AI 對話

在 `requirement` 階段，你需要回答 specist 的問題，直到信心度達到 95%。

**範例對話**：
```
specist: 我理解你需要專案審核流程。以下幾點需要確認：
         1. 審核階段有哪些？（例：初審、複審、終審）
         2. 誰可以執行審核？
         3. 審核需要哪些欄位？

         目前信心度：65%

你: 審核分為「專案經理審核」和「財務審核」兩階段。
    專案經理可審核所屬專案，財務人員審核金額。
    需要記錄審核意見和審核時間。

specist: 明白。還有幾個問題：
         1. 兩階段是否有順序？（必須先專案經理才能財務？）
         2. 審核不通過後，可以重新送審嗎？

         目前信心度：82%
```

### 繼續下一階段

當信心度達標後，輸入：

```
/continue
```

系統會自動進入下一階段並呼叫對應 Agent。

### 查看進度

隨時輸入：

```
/status
```

顯示當前任務進度、已完成階段、使用的 Agent。

---

## 任務類型

| 類型 | Command | 適用場景 | 完整流程 |
|------|---------|----------|----------|
| Feature | `/feature` | 新功能開發 | requirement → specification → testing → development → review → gate |
| Fix | `/fix` | Bug 修復 | requirement → testing → development → review → gate |
| Refactor | `/refactor` | 程式碼重構 | requirement → specification → testing → development → review → gate |
| Test | `/test` | 補充測試 | requirement → testing → gate |

### 選擇指南

- **新功能**：使用 `/feature`，會有完整的規格設計階段
- **Bug 修復**：使用 `/fix`，跳過規格設計，快速進入測試和修復
- **重構**：使用 `/refactor`，著重行為不變的驗證
- **補充測試**：使用 `/test`，最小流程，只寫測試不改代碼
- **大型功能**：使用 `/epic`，拆分為多個子任務

---

## Epic 管理

### 什麼是 Epic？

**Epic** 是大型功能，需要拆分為多個子任務（Feature/Fix/Test）才能完成。

### 何時使用 Epic？

當 Feature 符合以下條件時，建議上升為 Epic：

| 條件 | 閾值 |
|------|------|
| 跨 Domain 數量 | ≥ 3 個 |
| 需要前置調查/清理 | 有 |
| 預估驗收場景數 | > 15 個 |
| 無法單次交付完整價值 | 是 |

### Epic 建立流程

```
/epic sf_project, 發票折讓體系
         │
         ▼
┌─────────────────────────────────┐
│ specist: Epic Planning（提案）  │
│ • 識別涉及的 Domains           │
│ • 拆分 Phases                   │
│ • 識別子任務                    │
│ • 建立依賴關係                  │
└─────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────┐
│ 輸出提案，等待用戶確認         │
│ • 確認 → 建立 Epic + 子任務    │
│ • 調整 → 修改後重新確認        │
│ • 取消 → 放棄建立              │
└─────────────────────────────────┘
         │
         ▼ 確認後
┌─────────────────────────────────┐
│ 建立檔案：                      │
│ • Epic YAML                     │
│ • 子任務 JSON（T1.1, T1.2...） │
│ • 更新 MCP 任務狀態             │
└─────────────────────────────────┘
```

### Feature → Epic 上升流程

在 `/feature` 執行時，如果 specist 判斷範圍過大：

```
/feature sf_project, 實作折讓功能
         │
         ▼
    信心度評估（澄清）
         │
         │ 信心度 ≥ 95%
         ▼
    範圍評估 ← 這裡判斷是否上升 Epic
         │
    ┌────┴────┐
    │         │
 維持       建議上升 Epic
Feature    （詢問用戶）
    │         │
    ▼         ▼
 繼續      /epic ...
```

**注意**：範圍評估在信心度達到 95% **之後**才執行，避免在不理解需求的情況下做錯誤判斷。

### 執行 Epic 子任務

Epic 的子任務使用標準 command 執行，格式為 `{epic-id}:{task-id}`：

```bash
/feature core_web, erp-period-domain:T1-1    # 執行 Epic 子任務 T1-1
/fix core_web, erp-period-domain:T2-3        # 執行 Epic 子任務 T2-3
```

執行時會自動：
1. 讀取 `epic.yml` 取得任務定義
2. 檢查依賴（dependencies）是否已完成
3. 如果有未完成的依賴，提示用戶並阻止啟動
4. 建立任務 JSON（含 `epic` 字段關聯）
5. 更新 Epic 中該任務的 status 為 `developing`

### Epic 同步機制

當 Epic 子任務完成（`/done` 或 `/close`）時，系統會自動同步 Epic 狀態：

#### 同步內容

| 檔案 | 更新內容 |
|------|----------|
| `epic.yml` | task status → `completed`、metrics 更新 |
| `tasks.md` | 進度總覽、已完成任務清單、下一個任務指示 |

#### 識別方式

任務 JSON 中的 `epic` 字段用於關聯：

```json
{
  "epic": {
    "id": "erp-period-domain",
    "taskId": "T2-3",
    "phase": "Phase 2: 核心 UseCases"
  }
}
```

#### 進度追蹤

**重要**：Epic 的真實進度記錄在 `tasks.md`，而非 `epic.yml` 的 metrics。

`/status` 命令會從 `tasks.md` 讀取進度顯示：

```markdown
| 指標 | 數值 |
|------|------|
| **已完成任務** | 14 / 32 |
| **進度百分比** | 44% |
| **當前 Phase** | Phase 2 進行中 |
| **下一個任務** | T2-3: 實作 ExportPeriod UseCase |
```

### 查看 Epic 進度

```bash
/status
```

輸出範例：

```
┌──────────────────────────────────────────────────────┐
│ 📊 sf_project 任務狀態                               │
├──────────────────────────────────────────────────────┤
│                                                      │
│ 🎯 Epic: 發票折讓體系                                │
│    進度：13/17 (76%)  ████████░░ 剩餘 4 tasks        │
│                                                      │
│    ✅ Phase 1: 調查確認      5/5                    │
│    ✅ Phase 2: 技術債清理    3/3                    │
│    🔄 Phase 4: 折讓體系建立  1/5                    │
│       ├─ ✅ T4.1 建立資料表                         │
│       ├─ ⏳ T4.2 實作 AR Allowance (可開始)         │
│       └─ 🔒 T4.4 整合 EcPay (等待 T4.2, T4.3)      │
│                                                      │
└──────────────────────────────────────────────────────┘
```

### Epic 目錄結構

```
epics/
└── {project}/
    ├── active/           # 進行中的 Epic
    │   └── {epic-id}.yml
    └── completed/        # 已完成的 Epic
        └── {epic-id}.yml

tasks/
└── {project}/
    ├── active/
    │   ├── T1.1.json     # Epic 子任務
    │   └── T4.2.json
    └── completed/
```

---

## 工作流程詳解

### 階段說明

#### 1. Requirement（需求釐清）

**目標**：確保需求明確，達到足夠信心度

**Agent**：specist

**你需要做的事**：
- 回答 specist 的問題
- 提供業務背景和限制條件
- 確認假設是否正確

**何時結束**：信心度達到門檻（全部 95%）

---

#### 2. Specification（規格設計）

**目標**：建立正式的功能規格

**Agent**：specist

**產出**：
- Given-When-Then 格式的驗收條件
- 邊界案例定義
- 錯誤處理規格

**你需要做的事**：
- 審核規格是否正確
- 確認邊界案例是否完整

---

#### 3. Testing（測試調整）

**目標**：生成測試代碼

**Agent**：tester

**產出**：
- 測試檔案（RSpec/Jest/Pytest）
- 測試骨架（先 pending）

**你需要做的事**：
- 確認測試覆蓋所有驗收條件
- （可選）調整測試細節

---

#### 4. Development（開發）

**目標**：實作代碼讓測試通過

**Agent**：coder

**產出**：
- 業務邏輯代碼
- 通過的測試

**你需要做的事**：
- 通常無需介入
- 如果測試反覆失敗，可能需要協助

---

#### 5. Review（結果審查）

**目標**：確保代碼品質

**Agents**：
- style-reviewer（代碼風格）
- risk-reviewer（安全/效能）

**產出**：
- 審查報告
- 評分（A/B/C/D）

**你需要做的事**：
- 審核報告
- 決定是否接受（可要求修正）

---

#### 6. Gate（品質門檻）

**目標**：最終品質把關

**Agent**：gatekeeper

**檢查項目**：
- 所有測試通過
- 審查評分達標
- 規格對照完整
- 無遺漏的 TODO

**你需要做的事**：
- 確認 Go/No-Go 決定
- 簽核完成

---

## 6 Agent 架構

### specist（規格專家）

**職責**：
- 需求分析與澄清
- 信心度評估
- 撰寫 Given-When-Then 規格
- 載入 Domain 知識

**工具**：Read, Glob, Grep, SlashCommand, WebSearch

**特點**：不能寫代碼，只能透過 spec-kit 寫規格

---

### tester（測試專家）

**職責**：
- 根據規格生成測試
- 執行測試並分析失敗
- 建議修復方向

**工具**：Read, Glob, Grep, Write, Edit, Bash

**支援框架**：RSpec, Jest, Pytest

---

### coder（開發專家）

**職責**：
- 實作業務邏輯
- 讓測試通過
- 遵循 DDD 架構

**工具**：Read, Glob, Grep, Write, Edit, Bash

**模式**：Entity, Service, Repository, Use Case

---

### style-reviewer（風格審查）

**職責**：
- 檢查命名規範
- 檢查語言慣用法
- 計算複雜度
- 評分（A/B/C/D）

**工具**：Read, Glob, Grep（唯讀）

**參考**：`style-guides/` 下的語言指南

---

### risk-reviewer（風險審查）

**職責**：
- 安全漏洞檢查（OWASP Top 10）
- 效能問題檢測
- 風險評估（Critical/High/Medium/Low）

**工具**：Read, Glob, Grep（唯讀）

---

### gatekeeper（品質把關）

**職責**：
- 檢查所有品質門檻
- Go/No-Go 決策
- 知識策展（新規則記錄）

**工具**：Read, Glob, Grep, Write

**門檻**：
- Test Gate: 所有測試通過
- Review Gate: 評分 ≥ C
- Spec Gate: 規格完整對照
- Doc Gate: 無遺漏 TODO

---

## Commands 參考

### 任務啟動

| Command | 說明 | 範例 |
|---------|------|------|
| `/feature {project}, {title}` | 新功能 | `/feature sf_project, 專案審核` |
| `/fix {project}, {title}` | Bug 修復 | `/fix core_web, 登入錯誤` |
| `/refactor {project}, {title}` | 重構 | `/refactor sf_project, 移除舊報表` |
| `/test {project}, {title}` | 補測試 | `/test sf_project, 審核服務測試` |
| `/epic {project}, {title}` | 大型功能（Epic） | `/epic sf_project, 發票折讓體系` |

### 任務控制

| Command | 說明 | 使用時機 |
|---------|------|----------|
| `/continue` | 進入下一階段 | 當前階段已完成 |
| `/status` | 查看進度（含 Epic） | 任何時候 |
| `/abort` | 放棄任務 | 不想繼續 |

---

## Metrics 追蹤

系統會自動追蹤每個 Agent 的資源消耗。

### 追蹤的指標

| 指標 | 說明 | 範例 |
|------|------|------|
| **Tool Uses** | Agent 使用的工具次數 | 21 |
| **Tokens** | Token 消耗量 | 41.9k |
| **Duration** | 執行時間 | 2m 12s |

### 查看方式

#### 1. `/status` 指令

```
═══ 使用的 Agents ═══

1. specist (需求分析)
   └─ 15 tools · 28.5k tokens · 1m 45s

2. tester (測試生成)
   └─ 21 tools · 41.9k tokens · 2m 12s

═══ 資源消耗 ═══
🔧 Tools：36
📊 Tokens：70.4k
⏱️ 時間：3m 57s
```

#### 2. JSON 任務檔

```json
{
  "agents": [
    {
      "name": "specist",
      "metrics": { "toolUses": 15, "tokens": 28500, "duration": "1m 45s" }
    }
  ],
  "metrics": {
    "totalToolUses": 54,
    "totalTokens": 105600,
    "totalDuration": "5m 42s"
  }
}
```

### 用途

- **成本分析**：了解每個任務的 token 消耗
- **效能優化**：找出耗時較長的階段
- **比較基準**：不同類型任務的資源需求

---

## 常見問題

### Q: 可以在階段轉移時 `/clear` 清理對話嗎？

**A**: 可以，而且建議這樣做。

ATDD 工作流程的 Agent 間 context 傳遞**不依賴對話記憶**，而是透過：
- 任務 JSON（`tasks/{project}/active/*.json`）
- 規格檔案
- 測試檔案
- E2E Fixtures

**安全的 clear 時機**：
```
✅ /continue 後、Agent 開始前
✅ /fix-critical、/fix-high、/fix-all 後
✅ 任何階段轉移完成時
```

**不建議 clear 的情況**：
```
⚠️ 階段進行中（例如還在和 specist 對話釐清需求）
⚠️ 你口頭提供了重要資訊但還沒被寫入任務 JSON
```

系統會在階段轉移時提示：`💡 可依序輸入：/clear → /continue 清理對話後繼續`

**`/clear` 後恢復流程**：
```
/clear（清空對話）
    ↓
/continue（系統讀取 JSON）
    ↓
如果有多個任務 → 列出選擇
如果只有一個 → 直接繼續
```

---

### Q: 可以跳過某些階段嗎？

**A**: 不建議。每個階段都有其目的：
- Requirement 確保方向正確
- Testing 確保行為正確
- Review 確保品質達標

跳過可能導致返工成本更高。

---

### Q: 測試一直失敗怎麼辦？

**A**: 系統允許 `testing` ↔ `development` 循環：
1. tester 分析失敗原因
2. coder 嘗試修復
3. 重新執行測試

如果循環太多次，可能需要回到 requirement 重新釐清需求。

---

### Q: 審查評分太低怎麼辦？

**A**: 有兩個選擇：
1. **修正**：回到 development 改善代碼
2. **接受**：如果有正當理由（如時程壓力），可選擇接受並記錄原因

---

### Q: 可以同時進行多個任務嗎？

**A**: 可以。系統支援多個 active 任務同時存在。

當有多個任務時，`/continue` 會列出所有 active 任務讓你選擇：

```
┌──────────────────────────────────────────────────────┐
│ 📋 發現多個進行中的任務                              │
├──────────────────────────────────────────────────────┤
│ 1. [sf_project] 專案審核流程 (testing)               │
│ 2. [core_web] 登入頁面修復 (requirement)             │
└──────────────────────────────────────────────────────┘
```

你也可以直接指定：`/continue sf_project` 或 `/continue {task_id}`。

> **建議**：雖然支援多任務，但同一時間專注於 1-2 個任務效率較高。

---

### Q: 如何查看歷史任務？

**A**:
- MCP：`/atdd-list` 或 `/status`
- 已完成：`tasks/{project}/completed/`
- 已失敗：`tasks/{project}/failed/`

---

### Q: 信心度是如何計算的？

**A**: specist 根據以下因素評估：

| 因素 | 說明 |
|------|------|
| 業務規則明確性 | 核心邏輯是否清楚 |
| 邊界條件定義 | 特殊情況是否處理 |
| 資料結構 | 輸入輸出格式是否明確 |
| 錯誤處理 | 異常情況是否定義 |
| 整合點 | 與其他系統的互動是否清楚 |

---

## 附錄：檔案結構

```
atdd-hub/
├── .claude/
│   ├── agents/           # Agent 定義
│   │   ├── specist.md
│   │   ├── tester.md
│   │   ├── coder.md
│   │   ├── style-reviewer.md
│   │   ├── risk-reviewer.md
│   │   └── gatekeeper.md
│   └── commands/         # Slash Commands
│       ├── feature.md
│       ├── fix.md
│       ├── refactor.md
│       ├── test.md
│       ├── epic.md       # Epic 管理
│       ├── continue.md
│       ├── status.md
│       └── abort.md
├── epics/                # Epic 記錄
│   ├── sf_project/
│   │   ├── active/
│   │   └── completed/
│   └── README.md
├── tasks/                # 任務記錄
│   ├── sf_project/
│   └── core_web/
├── style-guides/         # 代碼風格指南
│   ├── ruby.md
│   ├── python.md
│   └── javascript.md
├── domains/              # Domain 知識
├── docs/                 # 文檔
│   └── operation-manual.md
└── CLAUDE.md             # AI 指令
```
