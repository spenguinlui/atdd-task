---
description: 建立新的 E2E 測試套件
---

# Test Create: $ARGUMENTS

## 解析參數

格式：`{project}, {測試標題}`

有效專案：見 `.claude/config/projects.yml`

---

## 初始化流程

### 1. 生成 Suite ID

格式：`E2E-{prefix}{sequence}`

- 掃描 `tests/{project}/suites/` 現有套件
- 根據標題推斷 prefix（A=電費、B=租金、C=用戶應發...）
- 遞增 sequence

### 1.5 選擇 Executor

詢問用戶此套件支援哪些執行器：

```
選擇此套件的執行方式：
  1) Chrome MCP only（預設）— AI 驅動瀏覽器測試
  2) Capybara only — RSpec 自動化測試
  3) Both — 不同場景可用不同執行器
```

- 選 1：`executors.available: [chrome-mcp]`
- 選 2：`executors.available: [capybara]`，詢問 spec file 路徑
- 選 3：`executors.available: [chrome-mcp, capybara]`，詢問 spec file 路徑

若包含 capybara，設定 `executors.capybara.specFile`（預設 `spec/features/{suite_id}_spec.rb`）。

### 2. 建立套件目錄

```
tests/{project}/suites/{suite-id}/
├── suite.yml           # 套件定義
├── scenarios/          # 場景定義
├── fixtures/           # seed/cleanup 腳本
│   ├── seed.rb
│   └── cleanup.rb
└── runs/               # 執行記錄（初始為空）
```

### 3. 複製模板

- `suite.yml`：從 `acceptance/templates/suite.yml`
- `seed.rb`：從 `acceptance/templates/seed_tagged.rb.erb`（需 ERB 渲染）
- `cleanup.rb`：從 `acceptance/templates/cleanup_tagged.rb.erb`

### 4. 建立任務 JSON

參考：`shared/task-json-template.md`

特殊欄位：
```json
{
  "type": "test",
  "testPath": "tests/{project}/suites/{suite-id}/",
  "acceptance": {
    "profile": "e2e-suite"
  }
}
```

### 5. 更新 index.yml

新增套件到 `tests/{project}/index.yml`：
```yaml
suites:
  - id: "{suite-id}"
    title: "{title}"
    domain: null
    scenarios: 0
    lastRun: null
    lastStatus: null
```

---

## 呼叫 specist Agent

參考：`shared/agent-call-patterns.md`

**Prompt 重點**：
- 識別主要 Domain
- 定義測試範圍
- 規劃場景（Given-When-Then 格式）
- 定義前置條件與資料需求
- 信心度評估 >= 90%

**specist 產出**：
- 更新 `suite.yml`（domain、scenarios、validationCriteria）
- 建立場景 YAML（`scenarios/S1-xxx.yml`）
- 定義 setup/cleanup 需求

---

## 輸出格式

### 建立成功

```
═══════════════════════════════════════════════════════════
✅ 測試套件已建立

📋 套件資訊：
- ID: {suite-id}
- 標題: {title}
- 專案: {project}

📁 目錄：
tests/{project}/suites/{suite-id}/

📌 下一步：
1. specist 將分析需求並規劃場景
2. 確認場景後進入 testing 階段
3. tester 生成詳細步驟並執行 E2E

💡 可用指令：
- /test-run {project}, {suite-id} - 執行測試
- /test-list {project} - 查看所有套件
═══════════════════════════════════════════════════════════
```

---

## 與舊 /test 的差異

| 面向 | 舊 /test | 新 /test-create |
|------|----------|-----------------|
| 儲存位置 | `tests/{project}/{uuid}/` | `tests/{project}/suites/{suite-id}/` |
| 可重複執行 | ❌ 一次性 | ✅ 可重複 |
| 執行記錄 | 覆蓋 | 保存在 `runs/` |
| GIF 歷史 | 覆蓋 | 每次執行獨立保存 |
| 資料策略 | Prefix | Tagged Data |
| 結案方式 | `/close` | 套件持續存在 |

---

## 任務流程

```
/test-create 啟動
    │
    ▼
┌─────────────────┐
│ 1. REQUIREMENT  │ ← specist
│    識別範圍     │
│    規劃場景     │
└────────┬────────┘
         │ 信心度 >= 90%
         ▼
    ✅ 套件就緒
         │
         ▼ /test-run 執行
┌─────────────────┐
│ 2. TESTING      │ ← tester
│    執行 E2E     │
│    錄製 GIF     │
│    記錄結果     │
└────────┬────────┘
         │ 測試完成
         ▼
    ✅ 執行記錄保存
```

---

## 場景規劃指南

specist 規劃場景時應考慮：

1. **Happy Path 優先**：先定義主要成功路徑
2. **Critical 場景標記**：標記關鍵驗證點
3. **前置條件明確**：清楚定義 Given
4. **可獨立執行**：場景間盡量獨立
5. **資料需求明確**：定義 seed 腳本需建立的資料

### Executor 選擇指南

若套件支援 Both，specist 在規劃每個場景時需指定 `executor`：

| 場景特性 | 建議 Executor |
|---------|--------------|
| 視覺驗證（版面、樣式、動畫） | chrome-mcp |
| 彈窗、檔案下載、拖拉操作 | chrome-mcp |
| 資料 CRUD 流程、表單送出 | capybara |
| 回歸測試（需反覆跑） | capybara |
| 非同步等待（Sidekiq、WebSocket） | 視複雜度，簡單用 capybara，複雜用 chrome-mcp |

場景 YAML 的 `executor` 欄位：
```yaml
scenarios:
  - id: S1
    executor: chrome-mcp    # 需要視覺確認
  - id: S2
    executor: capybara      # 純資料流程，適合自動化
  - id: S3
    executor: null           # 未指定，跑 suite default
```
