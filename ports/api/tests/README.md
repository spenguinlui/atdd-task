# Tests

Integration tests，打真實 local DB 驗證完整 stack。

## 執行

```bash
cd ports/api
DATABASE_URL="postgresql://liu@localhost:5432/atdd" .venv/bin/pytest -v
```

## 測試檔案

| 檔案 | 說明 | 測試數 |
|---|---|---|
| `test_api_endpoints.py` | API endpoints + Dashboard 頁面 | 21 |
| `test_services.py` | Service 層函數直接呼叫 | 24 |

## 架構

- `conftest.py` — 初始化 DB pool（session scope），提供 `client` fixture
- 使用真實 DB，不 mock — 確保 SQL 查詢與 schema 一致
- DB pool 在整個 test session 共用，lifespan 的 `close_pool` 被 patch 為 no-op 避免中途關閉

## 新增測試的慣例

**Service test** — 直接 call service function，驗證回傳結構：
```python
def test_list_something(self):
    result = some_service.list_something("00000000-0000-0000-0000-000000000001")
    assert isinstance(result, list)
```

**API endpoint test** — 用 `client` fixture 打 HTTP：
```python
def test_list_something(self, client):
    resp = client.get("/api/v1/something")
    assert resp.status_code == 200
```

**Dashboard page test** — 驗證 HTML 回傳包含關鍵文字：
```python
def test_some_page(self, client):
    resp = client.get("/dashboard/some-page")
    assert resp.status_code == 200
    assert "Expected Title" in resp.text
```

## 前提

- Local PostgreSQL 需運行且 `atdd` database 存在
- DB user 需有讀取權限（local 用 `liu`）
