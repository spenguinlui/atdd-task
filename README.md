# ATDD Hub

AI-driven Acceptance Test-Driven Development 工作流程管理系統。

## 概述

**ATDD Hub** 是一個基於 Claude Code 的 AI 驅動開發框架，採用 **Command-Driven** 工作流程與 **6-Agent 專職架構**，實現從需求到交付的完整自動化開發流程。

## 核心特點

- **Command-Driven** - 所有任務透過 Slash Command 啟動
- **6-Agent 專職架構** - 各 Agent 各司其職，確保品質
- **信心度機制** - 需求不明確時主動澄清，不盲目實作
- **TDD 驅動** - 測試先行，代碼跟隨
- **品質門檻** - 多層審查確保交付品質

## 快速開始

### 啟動任務

```bash
/feature {project}, {標題}   # 新功能開發
/fix {project}, {標題}       # Bug 修復
/refactor {project}, {標題}  # 程式碼重構
/test {project}, {標題}      # 補充測試
/epic {project}, {標題}      # 大型功能（拆分為多個子任務）
```

**範例**：
```bash
/feature sf_project, 專案審核流程
/fix core_web, 登入頁面無法顯示
/epic sf_project, 發票折讓體系
```

### 控制任務

```bash
/continue   # 繼續到下一階段
/status     # 查看當前進度
/abort      # 放棄當前任務
```

### Review 後修復

```bash
/fix-critical   # 修復 Critical 問題
/fix-high       # 修復 Critical + High 問題
/fix-all        # 修復所有問題
```

## 6-Agent 架構

| Agent | 職責 | 階段 |
|-------|------|------|
| **specist** | 需求分析、信心度評估、規格撰寫 | requirement, specification |
| **tester** | 測試生成、執行、失敗分析 | testing |
| **coder** | DDD 元件實作、修復測試 | development |
| **style-reviewer** | 代碼風格審查、命名規範 | review |
| **risk-reviewer** | 安全漏洞、效能問題、風險評估 | review |
| **gatekeeper** | 品質門檻驗證、Go/No-Go 決策 | gate |

## 任務流程

### Feature 完整流程

```
requirement → specification → testing → development → review → gate
    ↓             ↓              ↓           ↓           ↓       ↓
 specist      specist        tester      coder    reviewers  gatekeeper
```

**階段說明**：

| 階段 | 說明 | 人類介入 |
|------|------|----------|
| requirement | 需求釐清、信心度評估 | ✅ 必須確認 |
| specification | Given-When-Then 規格 | ✅ 審核 |
| testing | 生成並執行測試 | ⚠️ 可能 |
| development | DDD 元件實作 | ❌ AI 執行 |
| review | 風格 + 風險審查 | ✅ 審核 |
| gate | 最終品質門檻 | ✅ 簽核 |

### Fix 簡化流程

```
requirement → testing → development → review → gate
    ↓           ↓           ↓           ↓       ↓
 specist     tester      coder   risk-reviewer gatekeeper
```

Fix 任務採用 **Discovery Source** 調查流程，根據問題來源選擇對應的調查工具鏈。

### 其他流程

| 類型 | 流程 | 特點 |
|------|------|------|
| Refactor | 完整 6 階段 | 強調行為不變性 |
| Test | requirement → testing → gate | 最簡流程 |
| Epic | planning → 子任務執行 | 大型功能拆分 |

## Epic 管理

### 什麼時候使用 Epic？

當 Feature 範圍過大時（信心度達 95% 後判斷）：

| 條件 | 閾值 |
|------|------|
| 跨 Domain 數量 | ≥ 3 個 |
| 需要前置調查/清理 | 有 |
| 預估驗收場景數 | > 15 個 |

### Epic 流程

```
/epic {project}, {標題}
         │
         ▼
    specist: Epic Planning（提案）
         │
         ▼
    用戶確認後建立 Epic + 子任務
         │
         ▼
    執行子任務：/feature {project}, T1.1
```

### Feature → Epic 上升

在 `/feature` 執行時，若 specist 判斷範圍過大：

```
信心度評估 → 信心度 ≥ 95% → 範圍評估 → 建議上升 Epic
                                    ↓
                              用戶選擇
                             ├─ 同意 → /epic
                             └─ 維持 → 繼續 Feature
```

**重要**：範圍評估在信心度達標**之後**執行，確保理解正確再判斷。

### 查看 Epic 進度

```bash
/status   # 整合顯示 Epic 與獨立任務進度
```

## 信心度機制

> 詳細說明請見 [信心度機制文檔](docs/confidence-mechanism.md)

系統使用**兩套信心度評估**，確保 AI 在關鍵決策點不會盲目前進：

| 信心度 | Agent | 保護對象 | 門檻 |
|--------|-------|----------|------|
| 需求信心度 | specist | 需求 → 規格的品質 | ≥ 95% 才可進入 specification |
| 知識信心度 | curator | Domain 知識庫寫入 | ≥ 95% 才可寫入（結構 ≥ 70% 可提案） |

兩套閘門皆為**硬阻擋**（不是軟提醒），維度與權重定義於 `.claude/config/confidence/`。

## ATDD 驗收框架

### 核心理念

> 每個功能/修復必須有至少一個驗收測試，直接反映「問題/需求是否被解決」。
>
> 詳細說明請見 [驗收 Profile 指南](docs/acceptance-profiles.md)

驗收測試關注**業務結果**，不關注技術實作細節。

### Feature Profiles（ATDD 導向）

根據「**如何才能有效驗收**」選擇 Profile，而非功能類型：

| Profile | 說明 | 執行器 | 適用場景 |
|---------|------|--------|----------|
| **e2e** | 端對端驗收 | Chrome MCP | 結果即時可見（< 60 秒）|
| **integration** | 整合驗收 | RSpec/Jest | 需要時間操作、Mock、併發模擬 |
| **unit** | 單元驗收 | RSpec/Jest | 純計算邏輯、規則驗證 |

### Profile 選擇決策樹

```
Q1: 結果是否可在畫面即時看到（< 60 秒）？
    YES → e2e
    NO  ↓
Q2: 是否需要時間操作（週結、月結）？
    YES → integration
    NO  ↓
Q3: 是否依賴外部服務且需要 Mock？
    YES → integration
    NO  ↓
Q4: 是否為純計算/規則邏輯？
    YES → unit
    NO  → integration
```

### 快速參考

| Profile | 範例場景 |
|---------|----------|
| e2e | 表單送出後頁面更新、搜尋後列表篩選、登入後跳轉 |
| integration | 週結算排程、外部 API 串接、跨 Domain 資料流、背景 Job |
| unit | 金額計算公式、日期轉換、權限規則、狀態機 |

### Fix Discovery Sources

Bug 修復的 14 種調查流程（D1-D19）：

| Profile | Discovery Sources |
|---------|-------------------|
| UI | D1, D2, D3, D19 |
| Data | D4, D14 |
| Worker | D5, D6 |
| Performance | D8, D9 |
| Integration | D10 |
| Alert | D7 |
| Security | D12, D13 |

每個 Discovery Source 定義了調查工具的執行順序，確保系統性地定位問題。

## 目錄結構

> 詳細說明請見 [domains/README.md](domains/README.md)

```
atdd-hub/
│
│── requirements/{project}/  # 需求文件（BA 分析產出）
│── specs/{project}/         # 規格文件（Given-When-Then 驗收條件）
│── tasks/{project}/         # 任務追蹤
│   ├── active/              #   進行中任務 JSON
│   ├── completed/           #   已完成任務
│   └── failed/              #   失敗任務
├── epics/{project}/         # Epic 管理（大型功能拆分）
├── tests/{project}/         # E2E 測試套件（Chrome 自動化）
│   └── suites/{suite-id}/   #   場景定義 + 執行記錄
│
├── domains/{project}/       # 領域知識庫
│   ├── domain-map.md        #   領域邊界與關係圖
│   ├── ul.md                #   專有名詞表
│   ├── business-rules.md    #   跨域商務規則
│   ├── strategic/           #   商務邏輯（PM 可讀）
│   └── tactical/            #   系統設計（工程師用）
├── knowledge/               # 知識存取規範與 Schema
├── debug-knowledge/         # Debug 經驗庫（踩坑紀錄）
│
├── acceptance/              # 驗收框架配置
│   ├── registry.yml         #   ATDD Profile 配置
│   ├── fix-profiles.yml     #   Fix 問題分類
│   ├── fix-discovery-flows.yml  # Bug 調查流程
│   ├── templates/           #   測試模板
│   └── tips/                #   E2E 測試技巧
├── style-guides/            # 程式碼風格指南（Ruby / JS / Python）
├── docs/                    # 操作文檔
│
└── .claude/                 # AI Agent 配置
    ├── agents/              #   6 個 Agent 定義
    ├── commands/            #   37 個 Slash Commands
    └── config/              #   專案配置
```

## 核心原則

### AI 決策原則

- **澄清 > 猜測** - 不確定時主動詢問
- **信心度 < 95%** → 必須澄清
- **涉及業務邏輯假設** → 立即停止詢問

### Fix 調查原則

- **Production 資料不可變** - 所有 Command 操作僅限 Local/Staging
- **Rails Runner 必須在 Read Code 之後** - 沒看過 code 怎麼知道要 run 什麼
- **Git History 放到最後一站** - 用盡所有 debug 方式才質疑 git 版本
- **信心度 ≥95% 才可修復** - 不確定時返回人類確認

### 系統環境保護

禁止未經許可修改系統環境：
- 套件安裝（bundle install, npm install, pip install）
- 版本切換（rbenv, nvm, pyenv）
- 設定檔修改（Gemfile, package.json）

## Workflow Hooks

工作流程自動檢查點：

| Hook | 觸發時機 | 檢查內容 |
|------|----------|----------|
| pre-specification | requirement → specification | 信心度 ≥ 95% |
| pre-testing | specification → testing | 規格存在、ATDD Profile 已選擇 |
| pre-development | testing → development | 驗收測試存在 |
| pre-review | development → review | 所有測試通過 |
| pre-gate | review → gate | 驗收測試通過 |
| post-gate | gate → completed | 知識更新提醒 |

## 專案配置

### 支援的專案

專案 ID 與路徑定義於 `.claude/config/projects.yml`。

### 測試框架

| 語言 | 框架 |
|------|------|
| Ruby | RSpec |
| JavaScript | Jest |
| Python | Pytest |

## 文檔索引

| 文檔 | 說明 |
|------|------|
| [操作手冊](docs/operation-manual.md) | 完整操作指南 |
| [Fix 工作流程](docs/fix-workflow.md) | Fix 任務詳細流程 |
| [信心度機制](docs/confidence-mechanism.md) | 需求/知識信心度維度與閘門詳解 |
| [Review 修復流程](docs/review-fix-workflow.md) | Review 後修復機制 |
| [Agent 定義](.claude/agents/) | 6 個 Agent 的職責定義 |
| [驗收 Profile 指南](docs/acceptance-profiles.md) | 驗收 Profile 索引頁 |
| [Feature 驗收 Profile](docs/feature-profiles.md) | 4 個 Feature Profile、選擇決策樹 |
| [Fix 驗收 Profile](docs/fix-profiles.md) | 7 個 Fix Profile、調查流程、Affected Layer 對照 |
| [Style Guides](style-guides/) | 代碼風格指南 |

## 授權

UNLICENSED (Private)

---

**ATDD Hub** - AI-Driven Development, Human-Quality Results
