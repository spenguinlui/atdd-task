# Services — Application Layer

業務查詢邏輯層，位於 Driving Adapters (routers) 和 Driven Adapter (db) 之間。

## 模組

| Service | 說明 | 消費者 |
|---|---|---|
| `task_service.py` | 任務 CRUD、看板查詢、causation 查詢 | tasks.py, views.py |
| `domain_service.py` | Domain CRUD、sidebar、health、couplings | domains.py, views.py |
| `knowledge_service.py` | 知識 CRUD、統計、UL terms | knowledge.py, views.py |
| `overview_service.py` | Dashboard 聚合查詢（趨勢、成本） | views.py |
| `report_service.py` | 報告 CRUD | reports.py |

## 設計原則

- **純函數**，不用 class — 維持簡潔，不過度工程
- **接收 primitives**（`org_id: str`, `project: str`），不依賴 Pydantic / FastAPI
- **org_id 由呼叫端傳入** — service 不知道自己服務哪個 org
- **唯一允許 import db 的地方** — routers 禁止直接碰 DB

## 新增 Service 函數的慣例

```python
def list_something(org_id: str, project: str = "", limit: int = 50) -> list[dict]:
    """一個 service 函數的典型簽名。"""
    conditions = ["org_id = %s"]
    params: list = [org_id]
    if project:
        conditions.append("project = %s")
        params.append(project)
    where = " AND ".join(conditions)

    with get_cursor() as cur:
        cur.execute(f"SELECT ... FROM ... WHERE {where}", params)
        return cur.fetchall()
```

## 未來演進

當需要支援多 org 資料來源時（local DB + remote API），可在 service 層加 routing：

```python
def list_tasks(org_id: str, ...) -> dict:
    if org_id == LOCAL_ORG:
        return _list_tasks_from_db(...)   # local PostgreSQL
    else:
        return _list_tasks_from_api(...)  # remote HTTP
```

上層 routers 完全不需要改動。
