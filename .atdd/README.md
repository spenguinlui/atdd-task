# `.atdd/` — 本地開發者設定

此目錄存放每位開發者個人的本地設定，**不會同步到團隊**。

## `user.json` — 知識寫入身份識別

當你透過 Claude Code 觸發 `/knowledge`、curator agent、或任何 MCP 寫入工具時，
系統會把你的身份記錄到 `knowledge_entries.updated_by` / `knowledge_nodes.updated_by`
/ `knowledge_node_revisions.changed_by` 等欄位，並以 `human:<name>` 格式儲存，
Dashboard 顯示時會自動轉成「by Wayne」這樣的可讀形式。

### 設定方式

複製 `user.example.json` 為 `user.json`，填入你的名字：

```bash
cp .atdd/user.example.json .atdd/user.json
```

編輯 `user.json`：

```json
{
  "name": "Wayne"
}
```

`user.json` 已加入 `.gitignore`，**不會被 commit**，每位開發者各自設定自己的。

### 身份解析優先順序

MCP server 啟動時會依以下順序解析身份（前者勝出）：

| 優先 | 來源 | 範例 | 用途 |
|------|------|------|------|
| 1 | `ATDD_USER` 環境變數 | `slack:U123ABC` | Bot/CI/orchestrator 明確指定 |
| 2 | `.atdd/user.json`（cwd） | `{"name": "Wayne"}` | 專案層級 |
| 3 | `~/.atdd/user.json`（home） | `{"name": "Wayne"}` | 全域層級 |
| 4 | `git config user.email` | `wayne@example.com` | Git 自動 fallback |
| 5 | `claude:unknown` | — | 完全無法解析時 |

### 格式約定

存進 DB 的 `updated_by` 字串前綴決定顯示方式：

| Prefix | 範例 | 顯示 |
|--------|------|------|
| `human:` | `human:Wayne` | `Wayne` |
| `slack:` | `slack:U123ABC` | `Slack: U123ABC` |
| `bot:` | `bot:domain-health-recalc` | `🤖 domain-health-recalc` |
| `claude:` | `claude:curator` | `claude:curator`（legacy）|

### 驗證設定生效

```bash
cd /path/to/atdd-task
python3 -c "
import sys; sys.path.insert(0, 'ports/mcp')
from identity import resolve_identity
print(resolve_identity())
"
# 預期輸出：human:Wayne
```

也可以直接打 dashboard 知識頁面，看任何最近的修改紀錄是否顯示為 `by <你的名字>`。

### 相關檔案

- `ports/mcp/identity.py` — 解析邏輯
- `ports/mcp/server_admin.py` — MCP 寫入工具自動注入
- `ports/api/main.py:_format_identity` — Dashboard 顯示 filter
