# E2E 自動化執行指南

## E2E 模式判斷

```
檢查 acceptance.e2eMode：
| e2eMode 值 | 行為 |
|------------|------|
| "auto" | 執行自動化 E2E 測試 |
| "manual" | 跳過 E2E，標記為人工驗證 |
| null/undefined | 提供選擇，等待用戶決定 |
```

## 後台登入前置（強制 — 別再被登入卡住）

> 4 個 Rails 專案的 E2E 幾乎都要先登入 admin 後台。local dev DB 常是 production dump，
> admin 密碼是 production hash（沒人知道）、可能開 OTP，**每次都卡在這**。
> **E2E 開始前一律先跑這支，把 admin 密碼正規化成 seed 版本 + 關 OTP + 解鎖**：

```bash
.claude/scripts/ensure-admin-login.sh <sf_project|jv_project|core_web|e_trading>
```

各專案登入帳密（= 該 repo `db/seeds`，腳本已對齊）：

| 專案 | email | 密碼 |
|------|-------|------|
| sf_project | admin@sunnyfounder.com | `admin123456` |
| jv_project | admin@sunnyfounder.com | `admin123456` |
| core_web | admin@sunnyfounder.com | `admin12345` |
| e_trading | admin@sunnyfounder.com | `test123456` |

> ⚠️ **安全界線**：把密碼打進登入表單這一步由「人」做（原廠安全規範禁止 agent 代填密碼）。
> agent 能做的是：跑上面腳本確保帳密可用 → 請業主在瀏覽器登入（帳密已知、5 秒）→ agent 接手後續 E2E 斷言。
> 跑完腳本後若 session 已登入則直接續跑；未登入就提示業主用上表帳密登入，不要卡在「不知道密碼」上空轉。

## 自動化 E2E 執行流程

```
0. 確保 admin 可登入（見上方「後台登入前置」）
   .claude/scripts/ensure-admin-login.sh {project}

1. Setup（資料準備）
   rails runner db/seeds/acceptance/{task}_setup.rb

2. 開始錄製
   gif_creator (action: "start_recording", tabId: {tabId})
   computer (action: "screenshot", tabId: {tabId})

3. 執行步驟
   ├── navigate → mcp__claude-in-chrome__navigate
   ├── click → mcp__claude-in-chrome__computer (left_click)
   ├── input → mcp__claude-in-chrome__form_input
   ├── wait → mcp__claude-in-chrome__computer (wait)
   └── screenshot → mcp__claude-in-chrome__computer (screenshot)

4. Verify Results（驗證結果）
   mcp__claude-in-chrome__read_page / find

5. 停止錄製並匯出
   computer (action: "screenshot", tabId: {tabId})
   gif_creator (action: "stop_recording", tabId: {tabId})
   gif_creator (action: "export", tabId: {tabId}, download: true, filename: "{task_id}_e2e.gif")

6. Teardown（清理，可選）
   rails runner db/seeds/acceptance/{task}_cleanup.rb
```

## Chrome MCP 工具對照

| Fixture Action | Chrome MCP Tool |
|----------------|-----------------|
| `navigate` | `mcp__claude-in-chrome__navigate` |
| `click` | `mcp__claude-in-chrome__computer` (left_click) |
| `input` | `mcp__claude-in-chrome__form_input` |
| `type` | `mcp__claude-in-chrome__computer` (type) |
| `wait` | `mcp__claude-in-chrome__computer` (wait) |
| `scroll` | `mcp__claude-in-chrome__computer` (scroll) |
| `screenshot` | `mcp__claude-in-chrome__computer` (screenshot) |
| `find` | `mcp__claude-in-chrome__find` |

## Chrome MCP 連線檢查（必須在 E2E 執行前進行）

```
# 1. 嘗試取得瀏覽器 context
tabs_context_mcp (createIfEmpty: true)

# 2. 若收到 "Browser extension is not connected" 錯誤：
#    → 告知用戶 Chrome MCP 未連線
#    → 建議用戶執行 /chrome 並選擇「Reconnect extension」
#    → 等待用戶確認後重試一次

# 3. 重試仍失敗：
#    → 不再重試，直接返回人類對話
#    → 告知用戶連線失敗，請手動排查後再試
#    → 不要重複呼叫 tabs_context_mcp 期待自動恢復
```

> **已知問題**：Chrome 擴充功能的 Service Worker 會在閒置後斷線。
> 這是常見的間歇性問題，用 `/chrome` reconnect 即可恢復。
> 若 reconnect 後仍失敗，請檢查 Chrome 擴充功能是否正常運作。

## E2E 執行程式碼範例

```
# 1. 取得瀏覽器 context（已通過連線檢查）
tabs_context_mcp (createIfEmpty: true)

# 2. 開始錄製
gif_creator (action: "start_recording", tabId: {tabId})
computer (action: "screenshot", tabId: {tabId})

# 3. 執行 fixture 步驟
navigate (url: "/login", tabId: {tabId})
computer (action: "screenshot", tabId: {tabId})

form_input (ref: "ref_email", value: "test@example.com", tabId: {tabId})
form_input (ref: "ref_password", value: "password", tabId: {tabId})
computer (action: "left_click", ref: "ref_submit", tabId: {tabId})
computer (action: "wait", duration: 2, tabId: {tabId})
computer (action: "screenshot", tabId: {tabId})

# 4. 驗證結果
read_page (tabId: {tabId}, filter: "interactive")

# 5. 停止錄製並匯出
computer (action: "screenshot", tabId: {tabId})
gif_creator (action: "stop_recording", tabId: {tabId})
gif_creator (action: "export", tabId: {tabId}, download: true, filename: "{task_id}_e2e.gif")
```

## 更新任務 JSON artifacts

E2E 執行完成後，更新任務 JSON 的 `acceptance.results.e2e`：

```yaml
acceptance:
  results:
    e2e:
      status: "passed"
      recording: "{task_id}_e2e.gif"
      executedAt: "2024-01-15T10:30:00Z"
      executedBy: "coder"
      duration: "45s"
```

> GIF 會下載到瀏覽器的下載資料夾。
