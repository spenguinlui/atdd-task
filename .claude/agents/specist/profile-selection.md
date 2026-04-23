# ATDD Profile 選擇指南

## ⚠️ E2E 預設原則（2026-04 起強制）

**E2E 預設是 `required`，工具預設 `chrome-mcp`。**

Specist 可建議 `skipped` 的限定情境：
- 純後端重構（無 UI、無對外可觀察變更）
- 單純 DB migration / schema 變更
- 純 job/worker/framework 內部改動
- 測試工具或 dev-only 配置

涉及以下必須 `required`：
- UI 變更（form、button、list、表格）
- 使用者互動流程
- 對外通訊（email、webhook、外部 API）
- 金流、資料敏感操作
- 權限 / 授權邏輯變更

Specist 只產出建議；最終由 `/continue` 向用戶 AskUserQuestion 確認。
Hook `enforce-e2e-decision.sh` 會阻擋未經決策的 requirement → specification 轉移。

---

## 測試分類原則

| 分類 | 性質 | 存放位置 | 觸發時機 |
|------|------|----------|----------|
| **E2E** | 單點驗收（任務形態） | atdd-hub 管理 | 任務驗收時觸發 |
| **Integration / Calculation / Unit** | 防守型城牆（回歸測試） | 各專案 repo 內 | CI/CD 自動觸發 |

> E2E 驗證「這個任務是否完成」，Integration/Unit 確保「既有功能不被破壞」。

## 決策樹

```
Q1: 結果是否可在畫面即時看到（< 60 秒）？
├── YES → 考慮 e2e
└── NO  → 往下判斷

Q2: 是否需要時間操作（週結、月結、延遲執行）？
├── YES → 使用 integration
└── NO  → 往下判斷

Q3: 是否依賴外部服務且需要 Mock？
├── YES → 使用 integration
└── NO  → 往下判斷

Q4: 是否為後端邏輯變更，無 UI 互動？
├── YES → 使用 calculation
└── NO  → 往下判斷

Q5: 是否為純計算/規則邏輯？
├── YES → 使用 unit
└── NO  → 使用 integration
```

## 快速參考

### e2e Profile

適用場景：
- 表單送出後頁面更新
- 點擊按鈕後顯示 Modal
- 搜尋後列表篩選
- 登入後跳轉頁面

不適用：
- 結果需等待超過 1 分鐘
- 依賴特定時間點（週結、月結）
- 依賴外部服務回應且不穩定

### integration Profile

適用場景：
- 上傳檔案後等待處理完成
- 週/月結算排程
- 外部 API 串接
- 跨 Domain 資料流
- 背景 Job 處理

Test Helpers：
- time: `travel_to`, `freeze_time`
- mock: `stub_request`, `allow().to receive`
- async: `perform_enqueued_jobs`

### calculation Profile

適用場景：
- Entity 方法邏輯變更
- 稅額計算、金額計算
- 業務規則判斷
- 資料轉換邏輯
- 無 UI 的 Service/UseCase 變更

驗證方式：Console 或 API

### unit Profile

適用場景：
- 金額計算公式
- 日期格式轉換
- 權限規則判斷
- 狀態機轉換

## 輸出格式

```markdown
📦 ATDD Profile：{profile}
📋 選擇原因：{reason}
🧪 驗證方式：
  • 驗收測試：{e2e/integration/unit}
  • 執行器：{chrome-mcp/rspec/jest}
  • 時間輔助：{需要/不需要}
  • Mock 輔助：{需要/不需要}
```
