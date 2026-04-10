# ATDD API Server

FastAPI 應用，提供 REST API + Server-Rendered Dashboard。

## 架構

```
ports/api/
├── main.py              # FastAPI app entry point
├── db.py                # PostgreSQL connection pool (driven adapter)
├── services/            # Application service layer (業務邏輯)
├── routers/             # Driving adapters (HTTP endpoints)
│   ├── tasks.py         # /api/v1/tasks — Task CRUD
│   ├── domains.py       # /api/v1/domains — Domain health CRUD
│   ├── knowledge.py     # /api/v1/knowledge — Knowledge entries + UL terms
│   ├── reports.py       # /api/v1/reports — Report CRUD
│   ├── views.py         # /dashboard/* — HTML pages (Jinja2 + HTMX)
│   ├── events.py        # /api/v1/events — SSE real-time updates
│   └── workers.py       # /api/v1/workers — Background worker triggers
├── templates/           # Jinja2 HTML templates
├── static/              # CSS, JS assets
└── tests/               # pytest integration tests
```

## 六邊形分層

| 層 | 目錄 | 職責 |
|---|---|---|
| Driving Adapters | `routers/` | 接收 HTTP 請求，回傳 JSON 或 HTML |
| Application Services | `services/` | 業務查詢邏輯，不依賴 HTTP framework |
| Driven Adapter | `db.py` | PostgreSQL 連線池 |

**規則：Routers 不得直接 import db。所有資料存取必須透過 services。**

## 啟動

```bash
cd ports/api
DATABASE_URL="postgresql://liu@localhost:5432/atdd" .venv/bin/uvicorn main:app --reload --port 8001
```

## 測試

```bash
cd ports/api
DATABASE_URL="postgresql://liu@localhost:5432/atdd" .venv/bin/pytest -v
```

## 環境變數

| 變數 | 預設值 | 說明 |
|---|---|---|
| `DATABASE_URL` | `postgresql://atdd:atdd@localhost:5432/atdd` | PostgreSQL 連線字串 |
| `ATDD_ORG` | `00000000-...-000000000001` | 本部署的 org_id |
| `REMOTE_DASHBOARD_URL` | (空) | 另一環境的 Dashboard URL，用於 org 切換 |
| `API_KEY` | (空) | 設定後啟用 API Key 驗證；空值 = 開發模式 |
