# /test 任務執行指南

## 任務類型辨識

tester 可能被呼叫執行兩種類型的測試任務：

| 類型 | 來源 | 識別方式 |
|------|------|----------|
| 一次性任務 | `/test-create`（舊 `/test`） | `type == "test"`, `testPath` 存在 |
| 套件執行 | `/test-run` | `operationMode == "test-run"`, `suiteId` 存在 |

---

## 套件執行模式（新結構）

當 prompt 包含 `operationMode: test-run` 時：

### 目錄結構

```
tests/{project}/suites/{suite-id}/
├── suite.yml           # 套件定義
├── scenarios/          # 場景定義
├── fixtures/           # seed/cleanup 腳本
└── runs/               # 執行記錄
    └── {timestamp}/
        ├── run.yml
        └── recordings/
```

### 執行流程

```
Phase 1: 準備（由 /test-run command 完成）
├── 生成 test_run_id
├── 建立 runs/{timestamp}/ 目錄
├── 執行 fixtures/seed.rb {test_run_id}
└── 建立初始 run.yml

Phase 2: 執行（tester 負責）
├── 讀取 suite.yml 和 scenarios/
├── 更新 run.yml status = "running"
├── 依場景 executor 分流執行：
│   ├── chrome-mcp 場景：
│   │   ├── 開始 GIF 錄製
│   │   ├── 執行步驟（Chrome MCP）
│   │   ├── 驗證結果
│   │   ├── 停止 GIF 錄製
│   │   └── 更新 run.yml 場景結果
│   └── capybara 場景：
│       ├── 執行 bundle exec rspec（spec file）
│       ├── 解析 JSON 結果
│       └── 更新 run.yml 場景結果
└── 更新 run.yml status = "passed/failed"

Phase 3: 清理（由 /test-run command 完成）
├── 執行 fixtures/cleanup.rb {test_run_id}
├── 更新 suite.yml stats
└── 建立 latest symlink
```

### Tagged Data 重要性

所有測試資料都會帶有 `test_run_id` 標記：
- Seed 腳本會將 `test_run_id` 寫入資料的 metadata
- Cleanup 腳本只清理有該標記的資料
- 不會影響其他測試或真實資料

---

## 一次性任務模式（舊結構，向下相容）

當任務 JSON 的 `type == "test"` 時：

### 目錄結構

```
tests/{project}/{test_id}/
├── test.yml
├── scenarios/
├── scripts/
└── screenshots/
```

### 執行流程

```
Phase 1: 生成場景詳細步驟
├── 讀取 test.yml 的 scenarios 清單
├── 為每個場景生成詳細的 scenario.yml
└── 生成 setup/cleanup 腳本

Phase 2: Preflight 檢查
├── ⚠️ 檢查 Git Branch（最優先）
├── 檢查環境（伺服器、資料庫）
├── 檢查資料（測試帳號）
└── 執行 setup script

Phase 3: 執行 E2E 測試
├── 更新 execution.currentScenario
├── 截圖：S{n}-00-start.png
├── 執行每個步驟（Chrome MCP）
├── 驗證預期結果
└── 截圖：S{n}-99-end.png

Phase 4: 彙總結果
├── 更新 results.summary
├── 生成 results.yml
└── 執行 cleanup script
```

---

## Chrome MCP 連線檢查（E2E 執行前必須進行）

在使用任何 Chrome MCP 工具之前，先呼叫 `tabs_context_mcp`。若收到 `"Browser extension is not connected"` 錯誤：

1. **不要重複呼叫** `tabs_context_mcp` 期待自動恢復
2. **告知用戶** Chrome MCP 未連線
3. **建議用戶執行** `/chrome` 並選擇「Reconnect extension」
4. 等待用戶確認後**重試一次**
5. **重試仍失敗 → 直接返回人類對話**，告知連線失敗請手動排查

> **已知問題**：Chrome 擴充功能的 Service Worker 會在閒置後斷線，這是常見的間歇性問題，用 `/chrome` reconnect 即可恢復。若 reconnect 後仍失敗，請檢查 Chrome 擴充功能是否正常運作。

---

## Chrome MCP 工具對照

| Action Type | Chrome MCP Tool |
|-------------|-----------------|
| navigate | `mcp__claude-in-chrome__navigate` |
| click | `mcp__claude-in-chrome__computer` (left_click) |
| input | `mcp__claude-in-chrome__form_input` |
| type | `mcp__claude-in-chrome__computer` (type) |
| wait | `mcp__claude-in-chrome__computer` (wait) |
| scroll | `mcp__claude-in-chrome__computer` (scroll) |
| screenshot | `mcp__claude-in-chrome__computer` (screenshot) |
| find | `mcp__claude-in-chrome__find` |
| read | `mcp__claude-in-chrome__read_page` |

---

## ⚠️ 彈出視窗處理規則（Chrome MCP 限制）

### 限制說明

Chrome MCP **只能操控同一個 tab group 內的分頁**。以下情況無法自動化：

| 情況 | 說明 | 處理方式 |
|------|------|----------|
| **Popup Window** | 點擊後開啟獨立瀏覽器視窗 | 人工介入 |
| **新視窗** | `window.open()` 開啟的新視窗 | 人工介入 |
| **跨 Tab Group** | 視窗不在 MCP tab group 中 | 人工介入 |

### 強制規則

> **遇到彈出視窗功能時，必須呼叫 `/test-pause` 請人工處理。**

這是 Chrome MCP 目前的技術限制，無法透過程式繞過。

### 🚫 絕對禁止的繞過行為

> **禁止用 `navigate` 將 popup URL 貼到主視窗來繞過 popup 限制。**

這樣做會導致：
1. 表單提交後 `window.close()` 關閉主視窗，測試中斷
2. 表單的回調/redirect 邏輯與主視窗不相容
3. 測試結果看似成功但實際資料未寫入

**同樣禁止**：
- 從 DOM 讀取 `href` 屬性後用 `navigate` 開啟
- 用 `javascript_tool` 修改 `target` 屬性繞過 popup
- 用 `window.open()` 模擬在同一 tab 開啟
- 任何試圖「解決」popup 限制的技術手段

**唯一正確做法**：暫停 → 人工操作 → 恢復。

### 識別方式（必須全部執行）

#### 點擊前識別（預防性）

1. **檢查場景 YAML**：步驟是否標記 `opensPopup: true`
2. **檢查元素屬性**：用 `read_page` 或 `find` 檢查按鈕是否有 `class="popup-window"`、`target="_blank"`、`onclick` 含 `window.open` 等特徵

#### 點擊後識別（防禦性）

執行 `click` 操作後，如果：

1. **頁面沒有變化**（URL 未改變），但應該要有反應
2. **呼叫 `tabs_context_mcp` 後**，新開的視窗沒有出現在 availableTabs 中

→ 判定為彈出視窗，**必須立即暫停**，不得嘗試繞過。

### 暫停流程

```
1. 截圖保存當前狀態
2. 更新 run.yml：
   - status: "paused"
   - pause.reason: "彈出視窗需人工介入"
   - pause.humanAction: "詳細的人工操作指示"
3. 輸出暫停訊息，列出人工需完成的步驟
4. 等待 /test-resume
```

### 人工操作指示範本

```markdown
┌──────────────────────────────────────────────────────────────┐
│ ⏸️ 測試已暫停 - 需人工處理彈出視窗                           │
├──────────────────────────────────────────────────────────────┤
│ 📍 暫停位置：{場景名稱} - {步驟描述}                         │
│                                                              │
│ 🔧 請在彈出視窗中完成以下操作：                              │
│    1. {操作 1}                                               │
│    2. {操作 2}                                               │
│    3. {操作 3}                                               │
│    4. 完成後關閉彈出視窗                                     │
│                                                              │
│ 📝 完成後輸入 /test-resume 繼續測試                          │
└──────────────────────────────────────────────────────────────┘
```

### 場景 YAML 標記（建議）

在場景定義中標記可能觸發彈出視窗的步驟：

```yaml
steps:
  - id: 5
    action: "click"
    selector: "新增週期"
    opensPopup: true          # 標記會開啟彈出視窗
    humanIntervention: true   # 需要人工介入
    humanAction: |
      1. 選擇週期類型
      2. 確認日期
      3. 點擊確定
    description: "點擊後會開啟新視窗，需人工操作"
```

tester 執行時若遇到 `opensPopup: true`，應主動暫停並提示人工介入。

---

## ⚠️ 需轉人工 E2E 的情況

以下情況 Chrome MCP 無法自動化驗證，必須轉為人工 E2E：

| 類型 | 原因 | E2E 自動化範圍 |
|------|------|----------------|
| **外部應用程式結果** | Chrome MCP 無法存取瀏覽器以外的應用 | 執行到「觸發動作」為止 |
| **檔案下載內容** | Chrome MCP 無法存取本機檔案系統 | 執行到「點擊下載」為止 |

### 強制規則

> 1. **外部應用程式**：當驗證需要檢查外部應用程式結果（如 Slack、Email、第三方服務回應）時，E2E 只執行到觸發動作，後續由人工驗證。
>
> 2. **檔案下載**：當驗證需要檢查下載檔案的內容時，E2E 只執行到點擊觸發下載，檔案內容由人工驗證。

### 場景 YAML 標記

```yaml
# 觸發外部應用程式
- id: 5
  action: "click"
  triggersExternal: true      # 會觸發外部應用程式
  humanVerification: true     # 後續需人工驗證

# 觸發檔案下載
- id: 6
  action: "click"
  triggersDownload: true      # 會觸發檔案下載
  humanVerification: true     # 檔案內容需人工驗證
```

### 🚫 禁止僅用 DB 驗證替代檔案驗證

> **當場景標題或描述包含「驗證匯出檔案」、「驗證下載」等字樣時，
> 不得僅做 DB 查詢就標記為 passed。**

這類場景的重點是驗證**檔案內容**，DB 驗證只是輔助。正確做法：

1. 先做 DB 驗證（確認匯出狀態、時間戳等）
2. **必須暫停**，請人工下載並檢查檔案內容
3. 人工確認後才能標記 passed
4. 若無法取得檔案（如 presigned URL 過期），標記為 `partial` 並記錄原因

```
⏸️ 測試已暫停 - 需人工驗證匯出檔案

📍 暫停位置：{場景名稱}

🔧 請完成以下操作：
   1. 下載匯出的檔案（從 Slack 通知或系統介面取得）
   2. 開啟檔案確認：
      - 頁籤/Sheet 數量是否正確
      - 資料筆數是否符合預期
      - 欄位內容是否完整
   3. 回報驗證結果

📝 完成後輸入 /test-resume 繼續測試
```

**判斷依據**：場景名稱含以下關鍵字時，視為檔案驗證場景：
- 「驗證匯出檔案」「verify export file」
- 「驗證下載」「verify download」
- 「檢查檔案內容」「check file content」
- 場景 YAML 有 `triggersDownload: true` 或 `humanVerification: true`

### 替代方案

如果需要自動化驗證檔案內容或外部結果，應改用 **Integration Profile**（透過測試框架直接驗證資料/檔案）。

---

## Capybara 執行模式

當場景的 executor 為 `capybara` 時，tester 不使用 Chrome MCP，而是透過 RSpec 執行。

### 執行指令

```bash
cd {project_path} && bundle exec rspec {spec_file} --format documentation --format json --out {run_dir}/capybara_results.json
```

- `spec_file`：從 `suite.yml` 的 `executors.capybara.specFile` 取得
- Capybara spec 存放在各專案的 `spec/features/` 目錄

### 結果解析

讀取 `capybara_results.json`，將每個 example 映射到對應場景，記錄到 run.yml：
```yaml
scenarios:
  - id: "S1"
    executor: "capybara"
    status: "passed"         # 從 JSON 的 example status 映射
    duration: "12s"
    specOutput: "..."        # RSpec 輸出摘要
```

### 專案環境注意事項

#### Ruby 版本
各專案用 RVM 管理 Ruby 版本，執行前需確保在正確目錄下：
```bash
source "$HOME/.rvm/scripts/rvm" && rvm use $(cat {project_path}/.ruby-version)
```

#### Chromedriver（本機環境）
- `webdrivers` gem（<= 5.3.1）已 deprecated，無法處理 Chrome 115+
- 本機需手動安裝 chromedriver：`brew install chromedriver`
- 若 Gatekeeper 擋住，從 Chrome for Testing 手動下載對應版本
- `selenium-webdriver` 4.x 需要 Ruby >= 3.0，舊專案（Ruby 2.x）無法升級

#### Capybara Driver 設定
各專案的 `spec/support/capybara.rb` 需註冊 Chrome driver：
- 預設用 `chrome_headless`（本機），`firefox_headless`（CI）
- `ENV['CAPYBARA_DRIVER']` 可覆蓋
- 下載目錄設定在 driver preferences 中（`tmp/downloads`）

#### Pundit / 權限 Fixture
Admin 後台頁面通常需要 Pundit 授權。`Fixtures::Admin.run` 建立的帳號可能缺少特定頁面的存取權限。
撰寫 feature spec 時需確認 admin 帳號有對應的 role/permission。

---

## GIF 錄製規範

### 檔案命名與儲存

| 結構 | 儲存位置 | 命名格式 |
|------|----------|----------|
| 新結構 | `runs/{timestamp}/recordings/` | `S{n}-{scenario-name}.gif` |
| 舊結構 | `tests/{project}/{test_id}/recordings/` | `{test_id}-S{n}-{scenario-name}.gif` |

### GIF 錄製流程

```
1. 場景開始前
   gif_creator (action: "start_recording", tabId: {tabId})
   computer (action: "screenshot", tabId: {tabId})  # 捕捉初始狀態

2. 執行步驟
   navigate / click / input / wait
   （每個操作自動被錄製）

3. 場景結束後
   computer (action: "screenshot", tabId: {tabId})  # 捕捉最終狀態
   gif_creator (action: "stop_recording", tabId: {tabId})
   gif_creator (action: "export", tabId: {tabId}, download: true,
                filename: "{filename}.gif")
```

### 錄製時機

| 時機 | 動作 |
|------|------|
| 場景開始 | `start_recording` + `screenshot` |
| 關鍵步驟後 | `screenshot`（加入額外幀）|
| 場景結束 | `screenshot` + `stop_recording` + `export` |

> GIF 會下載到瀏覽器的下載資料夾。執行完成後需手動移動到正確位置。

---

## 結果記錄

### 新結構（run.yml）

```yaml
status: "passed"           # running | passed | failed | aborted
completedAt: "ISO timestamp"

results:
  total: 6
  passed: 5
  failed: 1
  skipped: 0
  duration: "5m 32s"

scenarios:
  - id: "S1"
    status: "passed"
    duration: "45s"
    recording: "recordings/S1-login.gif"

issues:
  - id: "ISS-001"
    severity: "high"
    scenario: "S5"
    step: 3
    description: "按鈕無法點擊"
    screenshot: "recordings/S5-issue-001.png"

# /test-revise 填入
revisions:
  - id: "REV-001"
    scenario: "S2"
    step: 5
    field: "expectedResult.status"
    before: "草稿"
    after: "待審核"
    reason: "狀態名稱已更新"
    timestamp: "ISO timestamp"

# /test-knowledge 填入
knowledgeGaps:
  - id: "KG-001"
    scenario: "S3"
    step: 5
    domain: "ErpPeriod"
    description: "狀態命名不一致"
    status: "open"           # open | resolved
    screenshot: "recordings/S3-knowledge-KG-001.png"
    timestamp: "ISO timestamp"
```

### 舊結構（results.yml）

```yaml
summary:
  total: 6
  passed: 5
  failed: 1
  skipped: 0
  duration: "5m 32s"

scenarios:
  - id: "S1"
    status: "passed"
    duration: "45s"
```

---

## 問題發現回報

當步驟失敗或發現異常時：

1. **立即截圖**：保存錯誤現場
2. **更新結果**：記錄失敗資訊
3. **判斷問題類型**並提供對應選項：

### 問題分類指引

**先判斷：系統行為是否符合規格/預期？**

#### 系統行為錯誤（Bug）
- `/test-fix` - 開 Fix 票並繼續測試
- `/test-fix-stop` - 開 Fix 票並停止測試（嚴重問題）

#### 測試預期有誤（系統正確，測試錯）
- `/test-revise {原因}` - 修正場景預期值，暫停確認後繼續

#### 無法判斷（知識缺口）
- `/test-knowledge {domain}, {描述}` - 記錄知識缺口，暫停測試進行知識討論

#### 不是 Bug，是其他問題
- `/test-feature {描述}` - 缺少功能，建立 Feature 任務並繼續
- `/test-refactor {描述}` - 架構/效能問題，建立 Refactor 任務並繼續

#### 流程控制
- `/test-skip` - 跳過此步驟繼續測試
- `/test-pause` - 暫停等待人工介入
- `/test-fail` - 標記測試失敗

### 回報格式

提供選項時，應先簡述觀察到的問題，再列出建議的命令：
```
觀察：{描述看到的現象}
預期：{場景 YAML 中的預期}
判斷：{初步判斷問題類型}

建議選項：
  /test-fix {描述}         ← 如果是系統 bug
  /test-revise {原因}      ← 如果是測試預期有誤
  /test-knowledge {描述}   ← 如果需要釐清 domain 知識
  /test-skip               ← 如果要跳過繼續
```

---

## Resume 模式

當 prompt 包含 `operationMode: resume` 時：

1. 讀取暫停位置資訊
2. 跳過已完成的場景/步驟
3. 從 `currentScenario` + `currentStep` 繼續執行
4. 繼續使用相同的 `test_run_id`（Tagged Data）
