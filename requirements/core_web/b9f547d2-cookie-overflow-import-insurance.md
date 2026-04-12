# 批次匯入保險 CookieOverflow：flash 訊息超過 cookie 大小限制

> **Task ID**: b9f547d2-ae6b-453d-8597-4d3ba21701cd | **Type**: fix | **Project**: core_web | **Date**: 2026-04-10
> **Domain**: ElectricityAccounting::FixedCharge | **Confidence**: 97%

## Request

在批次匯入保險功能 `/charges_calculation/batch_create_insurance_fixed_charges/import_xlsx`，匯入 xlsx 檔案時（例如 `2月能享公共意外險(5萬)保險匯入範例($412).xlsx`），會出現錯誤：

```
ActionDispatch::Cookies::CookieOverflow in Admin::ElectricityAccounting::ChargesCalculation::BatchCreateInsuranceFixedChargesController#import_xlsx
```

Rails cookie 最大值為 4KB，當 flash 訊息超過限制時觸發。匯入功能應正常完成，即使有大量筆數或錯誤訊息也不應觸發 CookieOverflow。

## SA

### 根因分析

**問題程式碼**：`BatchCreateInsuranceFixedChargesController#import_xlsx` 第 71 行

```ruby
flash[:alert] = Array(result[:errors]).join("\n")
```

**觸發條件**：
- `ImportInsuranceXlsx#validate_rows` 方法逐行驗證，每行最多可產生 6 種錯誤訊息（案場名稱空白/找不到、保險類別空白/不合法、開始日空白、結束日空白、結束日早於開始日、金額空白/非整數/非正數）
- 每筆錯誤訊息格式為 `"第 N 行：{錯誤描述}"`，約 20-40 bytes
- 30+ 行無效資料 × 多個欄位錯誤 = 輕易超過 4KB
- 所有錯誤透過 `Array#join("\n")` 合併為單一字串，存入 `flash[:alert]`
- Rails flash 儲存在 cookie 中，cookie 上限 4KB，溢出即拋 `CookieOverflow`

### 涉及 Model/Table

- `IncomeExpense`（ElectricityAccounting::ChargesCalculation::FixedCharge::Models::IncomeExpense）
- `Project`（用於案場名稱查找）

### 資料來源與流向

1. 用戶上傳 xlsx 檔案 → Controller `import_xlsx` action
2. `ImportInsuranceXlsx#call` 解析 xlsx → 逐行驗證 → 收集 errors 陣列
3. Controller 將 `errors` 陣列 join 為字串 → 存入 `flash[:alert]` → redirect
4. Rails 將 flash 序列化到 cookie → 超過 4KB → CookieOverflow

### 既有機制

Controller 的 `import_xlsx` action 直接使用 `flash[:alert]` 傳遞所有錯誤訊息，沒有任何截斷或摘要機制。

### 改動範圍

- `slices/admin/controllers/admin/electricity_accounting/charges_calculation/batch_create_insurance_fixed_charges_controller.rb` — `import_xlsx` action 的錯誤訊息處理邏輯

### 修復策略

限制 flash 訊息大小，避免超過 cookie 容量。建議方案：

1. **截斷 + 摘要**：只顯示前 N 筆錯誤，附加「...共 M 筆錯誤」摘要
2. 例如：顯示前 10 筆錯誤，若超過 10 筆則附加 `"...等，共 {total} 筆錯誤，請修正後重新上傳"`
3. 確保 flash 訊息總長度不超過安全閾值（例如 3KB，預留其他 cookie 空間）

### Causation

- **discoveredIn**: production
- **rootCauseType**: feature-defect
- **originTask**: ae7a8e3c（批次匯入保險功能原始實作）
- **說明**: 原始 feature 實作時未考慮大量驗證錯誤累積超過 cookie 大小限制的情境

### 風險點

- 修改截斷邏輯時需確保用戶仍能理解哪些行有問題
- 需注意中文字元在 cookie 中經 URL encoding 後會膨脹約 3 倍
