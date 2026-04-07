# Feature 驗收 Profile 指南

Feature Profile 根據「**如何才能有效驗收**」來分類，而非功能類型。選擇依據是結果何時可見、是否需要模擬環境。

機器可讀的完整定義請見 `acceptance/registry.yml`。

---

## e2e — 端對端驗收

透過瀏覽器驗證完整用戶流程，結果即時可見。屬任務形態的單點驗收，由 atdd-hub 管理。

| 項目 | 說明 |
|------|------|
| **執行器** | Chrome MCP |
| **測試格式** | Gherkin（Given-When-Then） |
| **存放位置** | atdd-hub `tests/` 或 `acceptance/fixtures/` |

**適用條件**：
- 結果可在畫面即時看到
- 等待時間 < 60 秒
- 不需要時間操作（freeze/travel）
- 不需要 Mock 外部服務

**不適用條件**：
- 結果需等待超過 1 分鐘
- 依賴特定時間點（週結、月結）
- 依賴外部服務回應且不穩定
- 需要模擬併發/Race Condition

**範例場景**：表單送出後頁面更新、點擊按鈕後顯示 Modal、搜尋後列表篩選、登入後跳轉頁面

**⚠️ E2E 完整性規範**（詳見 `acceptance/tips/e2e-completeness.md`）：
- 禁止只驗證顯示，必須執行**操作 → 儲存 → 重新載入 → 驗證持久化**完整循環
- 同功能多頁面必須各自獨立測試（不同頁面可能有不同儲存路徑）
- 表單提交後必須驗證即時回應（非 500）+ 資料持久化

---

## integration — 整合驗收

透過測試框架驗證跨元件/跨 Domain 的業務結果。屬專案層級的回歸測試（防守型城牆），存放在各專案 repo 內，由 CI/CD 自動觸發。

| 項目 | 說明 |
|------|------|
| **執行器** | RSpec / Jest |
| **測試格式** | RSpec / Jest |
| **存放位置** | 各專案 `spec/domains/**/integration/` |

**適用條件**：
- 結果需等待超過 1 分鐘
- 需要時間操作（freeze/travel_to）
- 需要 Mock 外部服務
- 需要模擬併發/Race Condition
- 跨多個 Domain 的資料流驗證
- 背景作業/排程任務

**範例場景**：上傳檔案後等待處理完成、週/月結算排程、外部 API 串接、跨 Domain 資料流、背景 Job 處理

---

## calculation — 計算/邏輯驗收

驗證後端計算邏輯、業務規則，無 UI 互動。屬專案層級的回歸測試，由 CI/CD 自動觸發。

| 項目 | 說明 |
|------|------|
| **執行器** | RSpec / Jest |
| **測試格式** | RSpec / Jest |
| **存放位置** | 各專案 `spec/domains/**/` |

**適用條件**：
- 純後端邏輯變更
- 計算公式或業務規則
- Entity/Service 方法變更
- 無 UI 互動
- 結果需透過 Console 或 API 驗證

**範例場景**：Entity 方法邏輯變更（如 `b2b?` 判斷）、稅額計算、業務規則判斷（如路由選擇）、資料轉換邏輯、無 UI 的 Service/UseCase 變更

---

## unit — 單元驗收

驗證純邏輯計算、規則、演算法的正確性。屬專案層級的回歸測試，由 CI/CD 自動觸發。

| 項目 | 說明 |
|------|------|
| **執行器** | RSpec / Jest |
| **測試格式** | RSpec / Jest |
| **存放位置** | 各專案 `spec/domains/**/unit/` |

**適用條件**：
- 純計算邏輯（公式、演算法）
- 單一業務規則驗證
- Value Object 行為
- Domain Service 邏輯
- 不涉及 I/O 或外部依賴

**測試重點**：公式正確性、邊界值處理、異常輸入處理、精度驗證

**範例場景**：金額計算公式、日期格式轉換、權限規則判斷、狀態機轉換

---

## Profile 選擇決策樹

```
Q1: 結果是否可在畫面即時看到（< 60 秒）？
    YES → e2e
    NO  ↓
Q2: 是否需要時間操作（週結、月結、延遲執行）？
    YES → integration
    NO  ↓
Q3: 是否依賴外部服務且需要 Mock？
    YES → integration
    NO  ↓
Q4: 是否為後端邏輯變更，無 UI 互動，需要 Console 驗證？
    YES → calculation
    NO  ↓
Q5: 是否為純計算/規則邏輯？
    YES → unit
    NO  → integration
```
