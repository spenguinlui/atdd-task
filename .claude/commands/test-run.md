---
description: 執行測試套件
---

# Test Run: $ARGUMENTS

## 解析參數

格式：`{project}, {suite-id}` 或 `{project}, all` 或 `{project}, group:{name}`

- `{project}`：專案 ID（必填）
- `{suite-id}`：套件 ID（如 `E2E-A1`）
- `all`：執行所有套件
- `group:{name}`：執行指定群組

有效專案：見 `.claude/config/projects.yml`

---

## 執行流程

### 1. 載入套件

- 讀取 `tests/{project}/suites/{suite-id}/suite.yml`
- 驗證套件存在
- 若執行 `all` 或 `group:`，讀取 `index.yml` 取得套件清單

### 1.5 執行器選單（Executor Selection）

讀取 `suite.yml` 的 `executors.available` 和各場景的 `executor` 欄位：

**單一 executor（只有 chrome-mcp 或只有 capybara）→ 跳過選單，直接執行。**

**多 executor（available 包含兩種）→ 顯示選單：**

```
═══════════════════════════════════════
📋 選擇執行方式

Suite: {suite-id} - {title}

  #  │ 場景              │ Chrome MCP │ Capybara
─────┼───────────────────┼────────────┼──────────
  S1 │ {title}           │     ✅     │    ❌
  S2 │ {title}           │     ✅     │    ✅
  S3 │ {title}           │     ❌     │    ✅

選擇：
  1) Chrome MCP only  → 執行 S1, S2（有 chrome-mcp 的場景）
  2) Capybara only    → 執行 S2, S3（有 capybara 的場景）
  3) All              → 全部場景，各用指定的 executor
  4) Custom           → 逐場景選擇（僅雙支援場景可切換）
═══════════════════════════════════════
```

**選單邏輯：**
- 場景有 `executor: chrome-mcp` → 只出現在 Chrome MCP 欄
- 場景有 `executor: capybara` → 只出現在 Capybara 欄
- 場景 `executor: null`（未指定）→ 根據 `executors.available` 決定，若兩者都有則兩欄都 ✅
- 選擇 Custom 時，對雙支援場景逐一詢問用哪個 executor

**決定後記錄到 run.yml：**
- 全用同一種 → `executor.type: "chrome-mcp"` 或 `"capybara"`
- 混合使用 → `executor.type: "mixed"`，各場景記錄自己的 executor

### 2. 生成 Test Run ID

```
test_run_id = "run_{timestamp}_{random_hex}"
例如：run_20260120_143052_a7b3
```

### 3. 建立執行記錄

- 目錄：`tests/{project}/suites/{suite-id}/runs/{timestamp}/`
- 建立 `run.yml`（參考 `acceptance/templates/run.yml`）
- 建立 `recordings/` 目錄

### 4. 檢查 Dependencies

若 `suite.yml` 有 `dependencies.requires`：
- 確認前置套件已執行通過
- 未通過則提示並停止

### 5. 執行 Setup（Seed）

```bash
cd {project_path} && rails runner tests/{project}/suites/{suite-id}/fixtures/seed.rb {test_run_id}
```

- 記錄建立的資料數量
- 失敗則停止並提示

### 6. 依 executor 類型執行場景

根據步驟 1.5 決定的 executor 分配，分兩種路徑執行：

#### 6a. Chrome MCP 場景 → 呼叫 tester Agent

參考：`shared/agent-call-patterns.md`

**傳遞資訊**：
- suite.yml 內容
- test_run_id
- 場景清單（僅 executor=chrome-mcp 的場景）
- 執行設定

**tester 職責**：
- 載入各場景 YAML
- 使用 Chrome MCP 執行
- 錄製 GIF（每場景一個）
- 記錄結果到 run.yml
- 發現問題時提供控制選項

#### 6b. Capybara 場景 → 執行 RSpec

**執行指令**：
```bash
cd {project_path} && bundle exec rspec {spec_file} --tag {scenario_tag} --format documentation --format json --out {run_dir}/capybara_results.json
```

- `spec_file`：從 `suite.yml` 的 `executors.capybara.specFile` 取得
- `scenario_tag`：場景 ID 對應的 RSpec tag（如 `S1`、`S2`）
- JSON 輸出用於解析結果寫入 run.yml

**結果解析**：
- 讀取 `capybara_results.json`
- 將每個 example 的 status 映射到對應場景
- 記錄 duration、failure message

#### 6c. 執行順序

- **Chrome MCP 場景先執行**（需要人互動監控）
- **Capybara 場景後執行**（自動化，無需監控）
- 若場景間有 dependency，依 dependency 順序執行，不論 executor 類型

### 7. 執行 Cleanup

```bash
cd {project_path} && rails runner tests/{project}/suites/{suite-id}/fixtures/cleanup.rb {test_run_id}
```

- 根據 `suite.yml` 的 `cleanup.onFailure` 設定處理失敗情況

### 8. 更新統計

更新 `suite.yml` 的 `stats`：
- `totalRuns += 1`
- `lastRun = now`
- `lastStatus = result`
- 計算 `passRate`

更新 `index.yml` 的對應套件資訊

### 9. 建立 latest symlink

```bash
ln -sf {timestamp} tests/{project}/suites/{suite-id}/runs/latest
```

---

## 輸出格式

### 開始執行

```
🚀 開始執行測試套件

Suite: {suite-id} - {title}
Test Run ID: {test_run_id}
Executor: {chrome-mcp | capybara | mixed}
場景數: {count}

⏳ 執行 Setup...
✅ Setup 完成，建立 {n} 筆資料

▶️ 執行場景...
```

### 場景執行中

```
[S1] 🌐 前往電費帳款列表 ⏳          ← 🌐 = Chrome MCP
[S1] 🌐 前往電費帳款列表 ✅ (45s)
[S2] 🌐 篩選可加入 ERP 的帳款 ⏳
[S3] 🧪 Capybara 執行中... ⏳         ← 🧪 = Capybara
[S3] 🧪 Capybara ✅ (12s)
```

### 完成

```
═══════════════════════════════════════════════════════════
✅ 測試完成

📊 執行結果：
- 總場景：16
- 通過：14
- 失敗：2
- 跳過：0
- 耗時：8m 32s

❌ 失敗場景：
- S10: 開立發票 - 按鈕無法點擊
- S12: 同步發票 - 逾時

🧹 Cleanup：✅ 已清理 15 筆資料

📁 執行記錄：
tests/{project}/suites/{suite-id}/runs/{timestamp}/

🎬 錄製檔案：
- S1-navigate-to-list.gif
- S2-filter-accounts.gif
...

📋 下一步：
- /test-run {project}, {next-suite-id} — 執行下一個套件
- /test-history {project}, {suite-id} — 查看執行歷史
- /test-edit {project}, {suite-id} — 修改測試場景
═══════════════════════════════════════════════════════════
```

### 下一步選項（必須提供）

測試完成後，**必須**根據結果提供對應的下一步選項：

**全部通過時：**
```
📋 下一步：
- `/test-run {project}, {next-suite}` — 執行下一個相關套件（若有）
- `/test-history {project}, {suite-id}` — 查看執行歷史
- `/test-edit {project}, {suite-id}` — 修改場景定義
```

**有失敗場景時：**
```
📋 下一步：
- `/test-run {project}, {suite-id}` — 重新執行整個套件
- `/test-fix {描述}` — 為失敗場景建立 Fix 任務
- `/test-edit {project}, {suite-id}` — 修改場景定義（若測試預期有誤）
- `/test-history {project}, {suite-id}` — 查看執行歷史
```

**判斷下一個套件**：檢查同 parent 下是否有後續套件（如 E2E-A1a → E2E-A1b → E2E-A1c）。

---

## 執行控制 Commands

與 `/test` 任務相同：

| Command | 說明 |
|---------|------|
| `/test-pause` | 暫停等待人工介入 |
| `/test-resume` | 繼續暫停的測試 |
| `/test-skip` | 跳過當前場景 |
| `/test-fail` | 標記失敗並停止 |
| `/test-fix` | 開 Fix 票並繼續 |
| `/test-fix-stop` | 開 Fix 票並停止 |

---

## 錄製設定

GIF 錄製參數（在 `suite.yml` 的 `execution.settings`）：

```yaml
execution:
  settings:
    recording: true
    screenshotOnStep: true
    screenshotOnError: true
```

GIF 儲存位置：
```
runs/{timestamp}/recordings/S{n}-{scenario-name}.gif
```

---

## 錯誤處理

### Setup 失敗

```
❌ Setup 失敗

錯誤訊息：{message}

請選擇：
1. /test-run {project}, {suite-id} - 重新執行
2. 手動修復後再試
```

### 場景失敗

根據 `suite.yml` 的 `execution.settings.stopOnFirstFailure`：
- `false`：繼續執行其他場景
- `true`：停止並提示

### Cleanup 失敗

根據 `suite.yml` 的 `cleanup.onFailure`：
- `prompt`：詢問是否繼續
- `force`：忽略錯誤
- `skip`：跳過清理
