# ATDD Platform Evolution — 設計決策文件

> 此文件記錄 ATDD 從 CLI 工具演進為團隊品質平台的完整設計。
> 用於跨 session 延續開發 context。

## 背景

分析 259 筆任務數據發現：
- Gate 通過率 ≈ 100%，但 **True Completion Rate ≈ 70%**
- Fix : Feature 比 = 1:2（每做 2 個功能就要修 1 次）
- 多個 domain fix rate > 100%（修比做多）
- Fix cascade 現象：修一個壞另一個，連鎖三次
- 知識庫雙向寫入衝突（PM via Slack、Dev via Local）

## 核心架構決策

### Source of Truth 轉移
- **現在**：Git (atdd-hub) 是唯一 source of truth
- **未來**：PostgreSQL (API Server) 為 source of truth，Git 降為 version history + 備份

### API Server 為中央協調點
- 所有寫入透過 API（Slack Bot、Claude Code、Web Dashboard、Cron）
- Claude Code 透過 **ATDD MCP Server** 連接 API
- 知識庫改為 DB 段落級存儲，解決雙向寫入衝突（見 `docs/atdd-server/knowledge-sync-problem.md`）

### Hexagonal Architecture
- Inbound Ports: SlackPort, WebPort, MCPPort, CronPort
- Core: TaskService, DomainHealthService, CausationService, KnowledgeService, ReportService
- Outbound Ports: TaskRepository, KnowledgeRepository, NotificationPort, GitPort, CodeAnalysisPort

### Multi-Organization（多組織支援）
- 最外層 context boundary = Organization（公司 vs 個人 vs 其他）
- Core 不感知 org，org_id 像 request scope 從最外層傳入
- 每個 org 獨立的：projects, tasks, domains, knowledge, reports
- 每個 org 可自訂：gate 標準、health 閾值、部署策略、整合設定
- DB 用 `organizations` 表 + `org_id` FK 隔離
- Dashboard 用 org switcher 切換
- Claude Code MCP 用 `ATDD_ORG` env 指定
- 實作方式：Phase 2 DB schema 加 org_id，Phase 4 Dashboard 加 switcher

```
Organization: "公司"           Organization: "個人"
├─ core_web                   ├─ side-project
├─ sf_project                 ├─ open-source-x
├─ aws_infra                  └─ ...
├─ Server: EC2                ├─ Server: localhost or same EC2
├─ Gate: 嚴格(95%, E2E必要)   ├─ Gate: 輕量(85%, E2E可選)
└─ Team: PM, Dev, Manager     └─ Team: 只有自己
```

### CQRS Lite
- Write Path: Claude Code / Slack Bot → API → PostgreSQL
- Read Path: Dashboard / API → PostgreSQL
- File Sync: DB → File Generator → local files（Claude Code agent 讀取用）
- Git: 保留作為 version history + 備份

---

## Phase 0: 資料地基（不動架構）

### 0-1. Domain Name Normalization ✅ 完成
- Script: `.claude/scripts/domain-normalize.py`
- 統一 19 筆命名不一致的任務 JSON
- Mapping: ErpPeriod→Tools::ErpPeriod, DigiwinErp→Tools::DigiwinErp, Tool::Receipt→Receipt, ProjectManagement→Project::Management, infrastructure→InfrastructureAutomation
- 逗號分隔的多 domain 拆分為 domain + relatedDomains

### 0-2. Task JSON causation 欄位 ✅ 完成
- 更新 `task-json-template.md`：新增 `causation` 欄位
- 更新 `/fix` command：specist 調查階段填寫 causedBy、rootCauseType、discoveredIn
- 欄位設計：
  ```json
  "causation": {
    "causedBy": null | { "taskId": "", "commitHash": "", "description": "" },
    "rootCauseType": "feature-defect|fix-regression|legacy|unknown|environment|dependency",
    "discoveredIn": "production|staging|e2e|review|development",
    "discoveredAt": "",
    "timeSinceIntroduced": ""
  }
  ```

### 0-3. Domain Health Calculator ✅ 完成
- Script: `.claude/scripts/domain-health.py`
- 輸出: `~/atdd-hub/domain-health.json`（1694 行）
- 結果: 35 domains — 🟢 11 healthy, 🟡 21 degraded, 🔴 3 critical
- Top critical: ElectricityAccounting (35), Accounting::AccountsPayable (38)
- Top coupling: DigiwinErp↔ErpPeriod (29), ElecAccounting↔ErpPeriod (18)

### 0-4. Deployed/Verified/Escaped 狀態 ✅ 完成
- 擴充 `task-flow-diagrams.md`：gate → deployed → verified | escaped，含風險分級表
- 擴充 `task-state-update.md`：新增 Event 4/5/6（deployed/verified/escaped）
- 擴充 `workflow-router.sh`：gate 和 deployed 階段顯示新選項
- 新增 `/verify` command：確認 production 正常 → deployed → completed
- 新增 `/escape` command：回報 production 問題 → deployed → escaped，建議建 fix 票
- 檔案移動：active/ → deployed/ → completed/ 或 escaped/
- 向後相容：`/done` 傳統流程不受影響，`/done --deploy` 為新流程

---

## Phase 1: 核心引擎 ✅ 完成

### 1-1. Agent Context Injection ✅ 完成
- specist：Phase 1 Domain 識別後讀取 domain-health.json，degraded/critical 自動警告
- risk-reviewer：新增 Phase 4 Domain Impact Assessment，評估跨域風險
- gatekeeper：新增 Domain Health Gate，影響部署建議（healthy→/done, critical→/done --deploy）

### 1-2. Causation Tracer Script ✅ 完成
- Script: `.claude/scripts/causation-tracer.py`
- 功能：git blame → commit hash → 反查 task JSON（by commitHash 精確匹配 + commit message fuzzy 匹配）
- 用法：`python3 causation-tracer.py <repo-path> <file> <line> [hub-path]`

### 1-3. /domain-diagnose Skill ✅ 完成
- Command: `.claude/commands/domain-diagnose.md`
- 5 階段：任務健康度 → 程式碼品質(RuboCop/Reek/Flog) → 邊界分析 → 命名一致性 → 報告
- 輸出：結構化診斷報告含 Health Card、Code Quality、Boundary Violations、UL Alignment

---

## Phase 2: API Server + DB ⬜ 待做

### 2-1. PostgreSQL Schema
```sql
-- Core tables
tasks (id UUID PK, project, type, status, domain, description, causation JSONB, ...)
task_history (task_id FK, phase, timestamp, agent, note)
task_metrics (task_id FK, agent, tool_uses, tokens, duration)

-- Domain health
domains (id, project, name, health_score, status, calculated_at)
domain_couplings (domain_a, domain_b, co_occurrence_count)

-- Knowledge (段落級)
knowledge_entries (id, project, domain, file_type, section, content, version, updated_by, updated_at)
knowledge_terms (id, project, domain, english_term, chinese_term, context, source)

-- Reports
reports (id, project, type, period, data JSONB, created_at)
```

### 2-2. FastAPI Application
- 加到現有 `server/` 目錄
- REST API: /api/v1/tasks, /api/v1/domains, /api/v1/reports
- SSE: /api/v1/events

### 2-3. Data Migration
- 259 筆歷史任務 JSON → PostgreSQL
- Knowledge files → knowledge_entries + knowledge_terms

### 2-4. Slack Bot 切換
- `bot/app.py` 改為呼叫 API（不再直接寫檔）
- `git_sync.py` → API-triggered sync

---

## Phase 3: ATDD MCP Server ⬜ 待做

### 3-1. MCP Server 開發
- Python MCP Server，連接 API
- Tools: atdd_task_*, atdd_domain_*, atdd_causation_*, atdd_report_*
- Claude Code 的 `.claude/settings.json` 加入 MCP 設定

### 3-2. Skill/Command 遷移
- /fix, /feature, /done 等命令改為呼叫 MCP tools
- Agent 讀取知識改為 MCP tools
- File Generator: DB → local files（backward compat）

---

## Phase 4: Web Dashboard ⬜ 待做

### 4-1. 技術棧
- FastAPI + Jinja2 + HTMX + Chart.js
- SSE 即時更新
- 部署到現有 Nginx（/dashboard 路由）

### 4-2. 頁面
- Executive Overview（交付/品質/成本指標）
- Domain Health Map（heatmap + coupling graph）
- Task Board（取代 markdown kanban，含 deployed/verified）
- Causation Explorer（fix chain 視覺化）
- Domain Diagnostic Report（per-domain 詳情）

---

## Phase 5: 智慧閉環 ⬜ 待做

- Deployed auto-verify（cron: low-risk 7天自動、high-risk Slack 提醒）
- 週報/月報自動產生 + Slack 推送
- Domain health → 自動建議 refactor 票
- 靜態分析整合（RuboCop/Reek/Flog/Packwerk）
- Escape rate 回饋 → 校準 gate 標準
- 多專案對比分析
- 認證 + 角色權限（PM/Dev/Manager/Client）

---

## 技術選型

| 元件 | 選擇 | 理由 |
|------|------|------|
| API | FastAPI | 已有 Python server，async 支援 |
| DB | PostgreSQL | 多人 concurrent writes，JSONB 欄位 |
| Frontend | HTMX + Jinja2 + Chart.js | 不需 npm build，server-rendered |
| 即時更新 | SSE | 單向推送，比 WebSocket 簡單 |
| Claude Code 整合 | MCP Server | 原生整合，雙向 |
| 部署 | Docker Compose on EC2 | 現有基礎設施 |

## Domain Health Score 公式

| 維度 | 權重 | 計算 |
|------|------|------|
| Fix Rate | 30% | fix_count / feature_count |
| Coupling Rate | 25% | cross_domain_tasks / total_tasks |
| Change Frequency | 15% | 近 30 天任務數 / 總任務數 |
| Knowledge Coverage | 15% | 有知識文件 / 應有知識文件 |
| Escape Rate | 15% | discoveredIn=production / total |

閾值：healthy >= 70, degraded 40-69, critical < 40

---

## Docker Compose 最終形態

```yaml
services:
  db:        # PostgreSQL 16
  api:       # FastAPI (REST API + Dashboard + MCP Server)
  bot:       # Slack Bot (改為呼叫 API)
  worker:    # Background jobs (health calc, auto-verify, reports)
  nginx:     # Reverse proxy (/api, /dashboard, /mcp)
```
