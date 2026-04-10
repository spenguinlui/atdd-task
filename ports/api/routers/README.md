# Routers — Driving Adapters

HTTP endpoints，分為 REST API 和 Dashboard HTML 兩類。

## API Routers (JSON)

| Router | Prefix | 說明 |
|---|---|---|
| `tasks.py` | `/api/v1/tasks` | Task CRUD + history + metrics |
| `domains.py` | `/api/v1/domains` | Domain health + couplings |
| `knowledge.py` | `/api/v1/knowledge` | Knowledge entries + UL terms |
| `reports.py` | `/api/v1/reports` | Report CRUD |
| `events.py` | `/api/v1/events` | SSE real-time event stream |
| `workers.py` | `/api/v1/workers` | Background worker triggers |

## Dashboard Router (HTML)

| Route | 頁面 |
|---|---|
| `GET /dashboard/` | Overview — KPI、趨勢圖、成本分析 |
| `GET /dashboard/tasks` | Kanban Task Board |
| `GET /dashboard/domains` | Domain Health Map |
| `GET /dashboard/domains/{name}` | Domain Detail（health radar、fix timeline） |
| `GET /dashboard/knowledge` | Knowledge Browser（知識文件 + UL 術語） |
| `GET /dashboard/causation` | Fix Causation Chains |

## 規則

- **禁止 import db** — 所有資料存取透過 `services/`
- Router 職責：解析 HTTP 參數、呼叫 service、回傳 JSON 或渲染 template
- Pydantic model 只在 router 層定義，不傳入 service
- Dashboard 頁面支援 HTMX partial update（檢查 `HX-Request` header）
