# ATDD Hub 知識體系指南

> 幫助 PM 與工程師快速理解 ATDD Hub 的架構、知識管理方式、以及各目錄的用途。

**Last Updated**: 2026-02-11
**Maintained By**: Development Team + curator

---

## ATDD Hub 是什麼

ATDD Hub 是團隊的 **AI 驅動開發工作台**，管理從需求到交付的完整流程。它不是一個程式碼專案，而是一個「工作流程 + 知識」的中央倉庫，搭配多個實際程式碼專案（如 core_web、sf_project）協同運作。

```
ATDD Hub（本 Repo）              各程式碼專案（外部 Repo）
┌──────────────────────┐         ┌──────────────────┐
│ 需求、規格、任務追蹤   │         │ core_web         │
│ 領域知識庫            │ ──────▶ │  app/            │
│ E2E 測試套件          │         │  domains/        │
│ 驗收框架              │         │  spec/           │
│ Debug 經驗庫          │         └──────────────────┘
│ 風格指南              │         ┌──────────────────┐
│ Epic / 任務管理       │ ──────▶ │ sf_project       │
└──────────────────────┘         └──────────────────┘
```

---

## 目錄總覽

```
atdd-hub/
│
├── requirements/          # 需求文件（BA 分析產出）
├── specs/                 # 規格文件（Given-When-Then 驗收條件）
├── tasks/                 # 任務追蹤（MCP + 任務 JSON）
├── epics/                 # Epic 管理（大型功能拆分）
├── tests/                 # E2E 測試套件（Chrome 自動化）
│
├── domains/               # 領域知識庫（本目錄）
├── knowledge/             # 知識存取規範與 Schema
├── debug-knowledge/       # Debug 經驗庫（踩坑紀錄）
│
├── acceptance/            # 驗收框架配置
├── style-guides/          # 程式碼風格指南
├── docs/                  # 操作文檔
│
└── .claude/               # AI Agent 配置
    ├── agents/            #   6 個 Agent 定義
    ├── commands/          #   37 個 Slash Commands
    └── config/            #   專案配置
```

### 各目錄的角色

| 目錄 | 一句話說明 | 主要讀者 |
|------|-----------|---------|
| `requirements/` | 每個任務的需求分析，含商務背景、Domain、信心度 | PM、工程師 |
| `specs/` | 驗收規格，Given-When-Then 格式 | QA、工程師 |
| `tasks/` | 任務追蹤，透過 MCP 管理狀態和歷程 | 全員 |
| `epics/` | 大型功能的拆分計畫和子任務 | PM、架構師 |
| `tests/` | E2E 測試套件（場景定義 + 執行記錄） | QA、工程師 |
| **`domains/`** | **領域知識庫（商務邏輯 + 系統設計）** | **全員** |
| `knowledge/` | 知識存取的 Schema 和規範 | Agent 開發者 |
| `debug-knowledge/` | Debug 經驗庫（錯誤模式 → 解法） | 工程師 |
| `acceptance/` | 驗收框架、測試模板、E2E Tips | QA、工程師 |
| `style-guides/` | Ruby / JS / Python 風格指南 | 工程師 |
| `docs/` | 操作手冊、流程文檔 | 全員 |

---

## 任務的生命週期與文件產出

一個任務從啟動到完成，會在不同目錄留下文件：

```
/feature core_web, ERP 單據列表加欄位
    │
    ▼
┌─ requirement 階段 ─────────────────────────────┐
│  產出：requirements/core_web/{task-id}.md       │
│  內容：商務背景、Domain、信心度、確認的業務規則   │
└────────────────────────────────────────────────┘
    │
    ▼
┌─ specification 階段 ───────────────────────────┐
│  產出：specs/core_web/{task-id}.md              │
│  內容：Given-When-Then 驗收條件、ATDD Profile   │
└────────────────────────────────────────────────┘
    │
    ▼
┌─ testing 階段 ─────────────────────────────────┐
│  產出：tests/core_web/suites/{suite-id}/        │
│  內容：suite.yml + scenarios/ + fixtures/       │
└────────────────────────────────────────────────┘
    │
    ▼
┌─ development → review → gate ──────────────────┐
│  產出：程式碼提交到對應專案 Repo                  │
│  記錄：透過 MCP 更新任務狀態                       │
└────────────────────────────────────────────────┘
    │
    ▼
┌─ 知識更新 ─────────────────────────────────────┐
│  更新：domains/core_web/ 下的知識文件            │
│  內容：新發現的業務規則、Pitfall、概念           │
└────────────────────────────────────────────────┘
```

### 任務追蹤

每個專案透過 MCP 追蹤所有任務的狀態和執行摘要：

```
tasks/{project}/
├── active/                # 進行中的任務 JSON
├── completed/             # 已完成的任務 JSON
├── closed/                # 已關閉的任務 JSON
└── failed/                # 失敗的任務 JSON
```

---

## 領域知識庫（本目錄）

### 設計理念

知識庫採用 DDD（Domain-Driven Design）的 **Strategic / Tactical 分層**：

- **Strategic（戰略層）**：回答「做什麼、為什麼」，用業務語言撰寫，PM 可直接閱讀
- **Tactical（戰術層）**：回答「怎麼做」，包含技術細節，給工程師參考

### 目錄結構

```
domains/
├── TEMPLATE-strategic.md        # 戰略層模板
├── TEMPLATE-tactical.md         # 戰術層模板
├── TEMPLATE-ul.md               # 專有名詞表模板
├── TEMPLATE-business-rules.md   # 商務規則模板
├── TEMPLATE-domain-map.md       # 領域邊界圖模板
│
└── {project}/                   # 各專案的知識庫
    ├── domain-map.md            # 領域邊界與關係圖
    ├── ul.md                    # 專有名詞表
    ├── business-rules.md        # 跨域商務規則
    ├── strategic/               # 商務邏輯層
    │   └── {Domain}.md
    └── tactical/                # 系統設計層
        └── {Domain}.md
```

### 文件類型一覽

| 文件 | 用途 | PM 需讀 | 工程師需讀 |
|------|------|---------|-----------|
| `domain-map.md` | 全局的領域邊界與關係圖 | 是 | 是 |
| `ul.md` | 專有名詞表（統一術語理解） | 是 | 是 |
| `business-rules.md` | 跨域商務規則 | 是 | 是 |
| `strategic/{Domain}.md` | 單一 Domain 的商務邏輯 | **是** | 視需要 |
| `tactical/{Domain}.md` | 單一 Domain 的系統設計 | 不需要 | **是** |

---

### domain-map.md — 領域邊界與關係圖

**讀者**：PM、架構師

描述所有 Domain 的邊界和協作關係，包含：
- Domain 列表與類型（Core / Supporting / Generic）
- 每個 Domain 的職責和 Key Entities
- Mermaid 關係圖（Context Mapping）
- 資料流全景

---

### ul.md — 專有名詞表（Ubiquitous Language）

**讀者**：全員

按字母排列的專有名詞定義，確保團隊對業務術語有一致的理解。

**詞條格式**：

| 欄位 | 必要 | 說明 |
|------|------|------|
| 中文 | 必要 | 中文名稱 |
| 定義 | 必要 | 一段話定義，避免歧義 |
| 類型 | 必要 | Entity / Value Object / Aggregate / Concept |
| 相關 Entity/Component | 必要 | 程式碼中的 class 路徑 |
| 業務規則 | 選填 | 適用的規則 |
| 範例 | 選填 | 程式碼範例 |
| 注意事項 | 選填 | 容易搞混的地方 |
| 相關詞彙 | 選填 | 連結到其他詞條 |

---

### business-rules.md — 跨域商務規則

**讀者**：PM、工程師

記錄橫跨 2 個以上 Domain 的商務規則。單域規則記錄在對應的 `strategic/{Domain}.md`。

**規則 ID 前綴**：

| 前綴 | 類型 | 範例 |
|------|------|------|
| `CD-xxx` | Cross-Domain（跨域規則） | CD-002: ERP 憑單產生規則 |
| `VR-xxx` | Validation Rule（驗證規則） | VR-003: 週期編號唯一性 |
| `CR-xxx` | Constraint Rule（約束規則） | CR-010: RecordType 分類 |
| `ST-xxx` | State Transition（狀態轉移） | ST-002: ErpPeriod 狀態轉移 |

---

### strategic/{Domain}.md — 商務邏輯

**讀者**：PM、QA、Stakeholder

用業務語言撰寫，不含程式碼。固定章節：

| 章節 | 內容 |
|------|------|
| 商務目的 | 這個 Domain 為什麼存在 |
| 商務能力 | 能做什麼事（條列） |
| 範疇定義 | 包含什麼 / 不包含什麼（劃清邊界） |
| 核心概念 | 指向 ul.md 的關鍵詞彙 |
| 狀態流程 | Mermaid 狀態圖 + 轉移規則表 |
| 商務規則 | 適用的規則 ID 列表 |
| 商務依賴 | 上游（我們需要什麼）/ 下游（誰依賴我們） |
| 常見問題 | Q&A 釐清業務疑問 |

---

### tactical/{Domain}.md — 系統設計

**讀者**：工程師

包含技術實作細節。固定章節：

| 章節 | 內容 |
|------|------|
| Domain Model | Aggregate / Entity / Value Object 定義（含欄位、ASCII tree） |
| Invariants | 不變量（唯一索引、狀態約束等） |
| State Transitions | Mermaid 圖 + Trigger / Side Effects 表 |
| Domain Services | Service 列表，含 Purpose 和 Code Location |
| Use Cases | UseCase 表格（狀態變化、說明） |
| Integration 技術細節 | 上下游整合方式與錯誤處理 |
| Patterns & Anti-Patterns | Where / Why / Reference |
| Common Pitfalls | Symptom / Cause / Solution 三段式 |
| Infrastructure Notes | 資料庫分布等基礎設施 |
| Knowledge Gaps | 待補充項目（checkbox 追蹤） |

**Pitfall 範例**（三段式格式）：

```markdown
### Pitfall: ElectricBill 兩個 Bounded Context 混淆
**Symptom**: 引用錯誤的 ElectricBill Model
**Cause**: ElectricityBilling 和 ElectricityAccounting 各有同名的 ElectricBill
**Solution**: 明確使用完整命名空間
```

---

## 其他知識資產

### E2E 測試套件（tests/）

每個測試套件是一個獨立目錄：

```
tests/{project}/suites/{suite-id}/
├── suite.yml              # 套件定義（名稱、描述、關聯任務）
├── scenarios/             # 測試場景（步驟定義）
├── fixtures/              # 測試資料
│   ├── seed.rb            #   資料準備 Script
│   └── cleanup.rb         #   資料清理 Script
├── context/               # 測試上下文
└── runs/                  # 執行記錄（含截圖）
    └── {timestamp}/
```

### Debug 經驗庫（debug-knowledge/）

記錄團隊在 Debug 過程中累積的經驗，用標籤系統（Tag Taxonomy）索引：

| 標籤類別 | 說明 | 範例 |
|----------|------|------|
| fix_profile | 問題類型 | ui, data, worker, performance |
| layer | 影響層級 | presentation, application, domain, infrastructure |
| domain | 業務領域 | ElectricityBilling, Contract, ErpPeriod |
| error_pattern | 錯誤模式 | nil_class, record_not_found, timeout |
| symptom | 外顯症狀 | page_blank, data_inconsistent, job_failed |

### 驗收框架（acceptance/）

定義任務的驗收標準和測試策略：

| 文件 | 用途 |
|------|------|
| `registry.yml` | ATDD Profile 配置（e2e / integration / unit） |
| `fix-profiles.yml` | Fix 任務的問題分類 |
| `fix-discovery-flows.yml` | Bug 調查的標準流程（14 種 Discovery Source） |
| `templates/` | 測試模板（fixture、scenario、seed script） |
| `tips/` | E2E 測試技巧（Chrome MCP、選擇器、等待策略） |

### 風格指南（style-guides/）

程式碼風格規範，供 style-reviewer Agent 審查時參考：

- `ruby.md` — Ruby / Rails 風格指南
- `javascript.md` — JavaScript / TypeScript 風格指南
- `python.md` — Python 風格指南

---

## AI Agent 與知識的關係

6 個 Agent 各自讀取不同層次的知識：

| Agent | 職責 | 讀取的知識 |
|-------|------|-----------|
| specist | 需求分析 | domain-map.md + ul.md + business-rules.md + strategic/{Domain}.md + tactical/{Domain}.md + contexts/{Domain}.md |
| tester | 測試生成 | ul.md + business-rules.md + strategic/ |
| coder | 程式碼實作 | ul.md + business-rules.md + tactical/ |
| style-reviewer | 風格審查 | style-guides/ |
| risk-reviewer | 風險審查 | tactical/（Patterns & Pitfalls） |
| gatekeeper | 品質門檻 | 驗收結果彙總 |

**知識更新循環**：

```
任務完成 → curator 分析新發現 → 提出知識更新建議 → 人工審核 → 知識庫更新
```

---

## 知識維護

### 每份文件的共同格式

- 頂部：**Last Updated** 日期 + **Maintained By** 標記
- 底部：**Change History** 表格（Date / Change / Changed By / Reason）
- Tactical 文件額外有 **Knowledge Gaps**（checkbox 追蹤待補充項目）

### 更新方式

| 方式 | 適用情境 |
|------|---------|
| 直接編輯 | 工程師發現錯誤或補充細節 |
| `/knowledge {project}, {domain}` | 透過 AI 討論並更新知識 |
| 任務完成後 curator 自動提案 | 開發過程中發現的新知識 |

### 建立新 Domain 知識

1. 複製 `TEMPLATE-strategic.md` → `strategic/{Domain}.md`
2. 複製 `TEMPLATE-tactical.md` → `tactical/{Domain}.md`
3. 在 `ul.md` 加入新詞條
4. 在 `domain-map.md` 加入新 Domain 的邊界和關係

---

## 文檔索引

| 文檔 | 說明 |
|------|------|
| [README.md](../README.md) | ATDD Hub 主頁（工作流程、命令速查） |
| [操作手冊](../docs/operation-manual.md) | 完整操作指南 |
| [Fix 工作流程](../docs/fix-workflow.md) | Fix 任務詳細流程 |
| [Agent 定義](../.claude/agents/) | 6 個 Agent 的職責定義 |
| [風格指南](../style-guides/) | 程式碼風格指南 |
| [驗收框架](../acceptance/README.md) | 驗收標準與測試策略 |
| [知識存取規範](../knowledge/README.md) | Agent 知識讀寫的 Schema |
