# ATDD Platform — 驗收清單

> 測試前提：Docker Desktop 啟動、DB 運行、API Server 運行
> Base URL: `http://localhost:8000`

---

## 0. 環境啟動

- [ ] Docker Desktop 啟動
- [ ] `docker compose -f infrastructure/docker-compose.yml up db -d` — PostgreSQL 啟動
- [ ] 建立 API venv 並安裝 dependencies
- [ ] 執行 DB migrations (`data/db/migrate.py`)
- [ ] 匯入歷史資料 (`data/db/import_data.py --hub <atdd-hub-path>`)
- [ ] 啟動 API Server (`cd ports/api && uvicorn main:app --reload --port 8000`)
- [ ] `GET /health` 回傳 `{"status": "ok"}`

---

## 1. API — Tasks CRUD

| # | 測試項目 | 方法 | 端點 | 預期結果 |
|---|---------|------|------|---------|
| 1.1 | 建立任務 | POST | `/api/v1/tasks` | 201, 回傳 task UUID |
| 1.2 | 查詢任務列表 | GET | `/api/v1/tasks` | 200, 回傳 array |
| 1.3 | 篩選 project | GET | `/api/v1/tasks?project=core_web` | 只回傳該 project |
| 1.4 | 篩選 status | GET | `/api/v1/tasks?status=completed` | 只回傳該 status |
| 1.5 | 篩選 domain | GET | `/api/v1/tasks?domain=Receipt` | 只回傳該 domain |
| 1.6 | 分頁 | GET | `/api/v1/tasks?limit=5&offset=0` | 最多 5 筆 |
| 1.7 | 取得單一任務 | GET | `/api/v1/tasks/{id}` | 200, 回傳完整 task |
| 1.8 | 更新任務 | PATCH | `/api/v1/tasks/{id}` | 200, 欄位已更新 |
| 1.9 | 新增 history | POST | `/api/v1/tasks/{id}/history` | 201 |
| 1.10 | 查詢 history | GET | `/api/v1/tasks/{id}/history` | 回傳事件列表 |
| 1.11 | 記錄 metrics | POST | `/api/v1/tasks/{id}/metrics` | 201 |
| 1.12 | 不存在的 task | GET | `/api/v1/tasks/{random-uuid}` | 404 |

**測試 payload 範例 (1.1):**
```json
{
  "org_id": "00000000-0000-0000-0000-000000000001",
  "project": "core_web",
  "type": "feature",
  "domain": "Receipt",
  "description": "驗收測試用任務"
}
```

---

## 2. API — Domains

| # | 測試項目 | 方法 | 端點 | 預期結果 |
|---|---------|------|------|---------|
| 2.1 | 列出所有 domains | GET | `/api/v1/domains` | 200, 回傳 array |
| 2.2 | 篩選 project | GET | `/api/v1/domains?project=core_web` | 篩選正確 |
| 2.3 | 篩選 status | GET | `/api/v1/domains?status=critical` | 只回傳 critical |
| 2.4 | Upsert domain | PUT | `/api/v1/domains` | 200/201 |
| 2.5 | 取得單一 domain | GET | `/api/v1/domains/{id}` | 200 |
| 2.6 | 列出 couplings | GET | `/api/v1/domains/couplings/list` | 回傳 coupling 列表 |
| 2.7 | Upsert coupling | PUT | `/api/v1/domains/couplings` | 200/201 |

---

## 3. API — Knowledge

| # | 測試項目 | 方法 | 端點 | 預期結果 |
|---|---------|------|------|---------|
| 3.1 | 建立 entry | POST | `/api/v1/knowledge/entries` | 201 |
| 3.2 | 列出 entries | GET | `/api/v1/knowledge/entries` | 200 |
| 3.3 | 篩選 file_type | GET | `/api/v1/knowledge/entries?file_type=strategic` | 篩選正確 |
| 3.4 | 取得單一 entry | GET | `/api/v1/knowledge/entries/{id}` | 200 |
| 3.5 | 更新 entry | PATCH | `/api/v1/knowledge/entries/{id}` | version +1 |
| 3.6 | 刪除 entry | DELETE | `/api/v1/knowledge/entries/{id}` | 204 或 200 |
| 3.7 | 列出 UL terms | GET | `/api/v1/knowledge/terms` | 200 |
| 3.8 | Upsert term | PUT | `/api/v1/knowledge/terms` | 200/201 |

---

## 4. API — Reports

| # | 測試項目 | 方法 | 端點 | 預期結果 |
|---|---------|------|------|---------|
| 4.1 | 建立 report | POST | `/api/v1/reports` | 201 |
| 4.2 | 列出 reports | GET | `/api/v1/reports` | 200 |
| 4.3 | 篩選 type | GET | `/api/v1/reports?type=weekly` | 篩選正確 |
| 4.4 | 取得單一 report | GET | `/api/v1/reports/{id}` | 200 |

---

## 5. Dashboard 頁面

> 用瀏覽器打開，確認頁面正常渲染

| # | 頁面 | URL | 驗證重點 |
|---|------|-----|---------|
| 5.1 | Executive Overview | `/dashboard/` | 4 張 metric 卡片顯示數字、折線圖 + 長條圖有資料 |
| 5.2 | Overview 篩選 | `/dashboard/?period=30d` | 切換 period 後數據更新 |
| 5.3 | Overview project 篩選 | `/dashboard/?project=core_web` | 切換 project 後數據更新 |
| 5.4 | Domain Health Map | `/dashboard/domains` | 彩色方塊（綠/黃/紅）、coupling matrix 表格 |
| 5.5 | Domain Health 篩選 | `/dashboard/domains?project=core_web` | 只顯示該 project domains |
| 5.6 | Domain Detail | `/dashboard/domains/{domain_name}` | 雷達圖 5 維、Fix 時間線、Knowledge 甜甜圈圖 |
| 5.7 | Task Board (Kanban) | `/dashboard/tasks` | 8 欄看板、卡片有 task 資訊 |
| 5.8 | Task Board 篩選 | `/dashboard/tasks?type=fix` | 只顯示 fix 類型 |
| 5.9 | Task Detail Modal | 點擊看板上任意卡片 | 彈出 modal 顯示 task 詳情 + history timeline |
| 5.10 | Causation Explorer | `/dashboard/causation` | Fix chain 表格、summary 卡片（total fix / regressions） |
| 5.11 | 導航列 | 所有頁面 | 左側 nav 連結可正常切換頁面 |

---

## 6. SSE 即時更新

| # | 測試項目 | 方法 | 預期結果 |
|---|---------|------|---------|
| 6.1 | SSE 連線 | 瀏覽器開 Dashboard + DevTools Network | EventSource 連線到 `/api/v1/events/stream` |
| 6.2 | 接收 keepalive | 等待 30 秒 | 收到 `:keepalive` 註解 |
| 6.3 | 觸發事件 | 在另一個 terminal 用 curl POST 建立 task | Dashboard 收到 toast 通知 |

---

## 7. Workers (背景任務)

| # | 測試項目 | 端點 | 預期結果 |
|---|---------|------|---------|
| 7.1 | Weekly Report | `POST /api/v1/workers/weekly-report` | 回傳 report data (delivery/quality/cost) |
| 7.2 | Weekly Report 儲存 | `POST /api/v1/workers/weekly-report` body: `{"save": true}` | report_id 回傳，可在 `/api/v1/reports` 查到 |
| 7.3 | Domain Health Recalc | `POST /api/v1/workers/domain-health` | 回傳 recalculated count + summary |
| 7.4 | Domain Health dry-run | `POST /api/v1/workers/domain-health` body: `{"dry_run": true}` | 回傳結果但 DB 不變 |
| 7.5 | Auto-Verify | `POST /api/v1/workers/auto-verify` | 回傳 auto_verified + alerts count |
| 7.6 | Auto-Verify dry-run | `POST /api/v1/workers/auto-verify` body: `{"dry_run": true}` | 不實際變更 |

---

## 8. MCP Server

> 前提：MCP Server 啟動 (`ports/mcp/.venv/bin/python3 ports/mcp/server.py`)

| # | 測試項目 | MCP Tool | 預期結果 |
|---|---------|----------|---------|
| 8.1 | Health check | `atdd_health` | 回傳 ok |
| 8.2 | Task list | `atdd_task_list` | 回傳任務列表 |
| 8.3 | Task create | `atdd_task_create` | 建立成功 |
| 8.4 | Domain list | `atdd_domain_list` | 回傳 domain 列表 |
| 8.5 | Knowledge list | `atdd_knowledge_list` | 回傳 entries |
| 8.6 | Term upsert | `atdd_term_upsert` | 新增/更新 UL term |
| 8.7 | Report list | `atdd_report_list` | 回傳 reports |

> MCP 可透過 Claude Code 直接呼叫（`.mcp.json` 已設定）

---

## 9. Data Import

| # | 測試項目 | 指令 | 預期結果 |
|---|---------|------|---------|
| 9.1 | Dry-run | `python3 data/db/import_data.py --hub <path> --dry-run` | 顯示預計匯入數量，DB 不變 |
| 9.2 | Import tasks | `--tasks-only` | tasks + task_history 有資料 |
| 9.3 | Import knowledge | `--knowledge-only` | knowledge_entries + knowledge_terms 有資料 |
| 9.4 | Import health | `--health-only` | domains + domain_couplings 有資料 |
| 9.5 | 重複匯入 | 再跑一次 full import | 不報錯（ON CONFLICT 處理） |

---

## 10. DB Schema 完整性

| # | 測試項目 | SQL | 預期結果 |
|---|---------|-----|---------|
| 10.1 | migrations 表 | `SELECT * FROM schema_migrations` | 001, 002 已套用 |
| 10.2 | 預設 org | `SELECT * FROM organizations` | 有 '個人' org |
| 10.3 | task_type enum | `SELECT enum_range(NULL::task_type)` | 5 個值 |
| 10.4 | task_status enum | `SELECT enum_range(NULL::task_status)` | 含 extended 值 |
| 10.5 | updated_at trigger | 更新任一 task 後查 updated_at | 自動更新 |

---

## 11. 整合測試 — End-to-End 流程

| # | 場景 | 步驟 | 預期結果 |
|---|------|------|---------|
| 11.1 | 任務生命週期 | POST create → PATCH to developing → PATCH to gate → PATCH to deployed → PATCH to verified | 每步 status 正確，history 有記錄 |
| 11.2 | Escape 流程 | 建立 feature → deployed → 建立 fix (causedBy=feature_id) → escape | causation 連結正確，Causation Explorer 顯示 chain |
| 11.3 | Domain Health 連動 | 建立多筆 fix task → 觸發 domain-health recalc | domain health_score 下降 |
| 11.4 | Dashboard 即時更新 | 開 Dashboard → 另一 terminal POST task | Toast 通知出現 |
| 11.5 | Weekly Report 完整性 | 有資料後觸發 weekly-report | delivery/quality/cost 各欄位有值 |

---

## 快速測試腳本

啟動後可用以下 curl 快速驗證核心功能：

```bash
BASE=http://localhost:8000
ORG="00000000-0000-0000-0000-000000000001"

# Health
curl -s $BASE/health | python3 -m json.tool

# Create task
TASK_ID=$(curl -s -X POST $BASE/api/v1/tasks \
  -H "Content-Type: application/json" \
  -d "{\"org_id\":\"$ORG\",\"project\":\"core_web\",\"type\":\"feature\",\"domain\":\"Receipt\",\"description\":\"驗收測試\"}" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
echo "Created task: $TASK_ID"

# Get task
curl -s $BASE/api/v1/tasks/$TASK_ID | python3 -m json.tool

# List tasks
curl -s "$BASE/api/v1/tasks?project=core_web&limit=5" | python3 -m json.tool

# Update task
curl -s -X PATCH $BASE/api/v1/tasks/$TASK_ID \
  -H "Content-Type: application/json" \
  -d '{"status":"developing"}' | python3 -m json.tool

# Add history
curl -s -X POST $BASE/api/v1/tasks/$TASK_ID/history \
  -H "Content-Type: application/json" \
  -d '{"phase":"development","status":"developing","agent":"coder","note":"started coding"}'

# List domains
curl -s "$BASE/api/v1/domains?project=core_web" | python3 -m json.tool

# Trigger weekly report
curl -s -X POST $BASE/api/v1/workers/weekly-report \
  -H "Content-Type: application/json" \
  -d '{"project":"core_web"}' | python3 -m json.tool

# Trigger domain health recalc
curl -s -X POST $BASE/api/v1/workers/domain-health \
  -H "Content-Type: application/json" \
  -d '{"dry_run":true}' | python3 -m json.tool
```
