# ERP 週期重複加入已有週期的電費單，重複建立 ERP record

> **Task ID**: 6036600c-3b71-4232-bd01-6d2d1ee79ac8 | **Type**: fix | **Project**: core_web | **Date**: 2026-04-10
> **Domain**: Tools::ErpPeriod | **Confidence**: 95%

## Request

ERP 週期功能在建立週期時，會將已經屬於其他週期的電費單也重複加入一次，導致重複建立 ERP record。

預期行為：建立 ERP 週期時，應該排除已經有週期的電費單，只加入尚未歸入任何週期的電費單。

Discovery source: production

## SA

### 問題根因

Bug 發生在 `SourceIdsQuery` 層，具體位於三個 Query 類別：

1. **`Admin::ErpPeriod::SourceIdsQueries::ElectricityBillQuery`**
   - `source_ids_from_billing_bill_ids` 方法查詢所有符合篩選條件的 `ElectricBillAccount` IDs
   - **未排除已存在於任何 `erp_records` 中的 source**

2. **`Admin::ErpPeriod::SourceIdsQueries::RoofRentalQuery`**
   - 同樣問題：查詢 `RoofRentalAccount` IDs 時未排除已有 ERP record 的帳戶

3. **`Admin::ErpPeriod::SourceIdsQueries::DueQuery`**
   - 同樣問題：查詢 `DueDetail` IDs 時未排除已有 ERP record 的明細

### 為什麼重複檢查沒攔住

`InsertRecordsToPeriod#load_existing_records`（第 261-269 行）只檢查 **同一週期內** 的重複（`erp_period_id: period.id`），不檢查跨週期重複。這是幂等設計（同一批 source 重複送進同一週期不會出錯），但不防止跨週期的重複加入。

`erp_records` 表的 unique index `idx_erp_records_source_unique` 是 `(erp_period_id, source_type, source_id, record_type)`，允許同一 source 出現在不同週期。

### 資料流

```
用戶在列表頁選擇篩選條件 → InsertRecordsController#new
  → SourceIdsQuery.call(period_type, q)
    → ElectricityBillQuery.call(q)  ← BUG: 未排除已有 ErpRecord 的 source
  → 顯示確認頁面（含所有符合條件的 source_ids）← BUG: form views 顯示的數量也未過濾
  → 用戶按確認 → InsertRecordsController#create
    → InsertRecordsToPeriod.call(erp_period_id, sources)
      → 每個 source 建立 ErpRecord + Document
```

### Form Views 也受影響

建立週期的 form 頁面呈現的待加入筆數與清單，同樣沒有排除已有週期的 source。用戶在確認頁看到的數量是未過濾的，導致用戶無法得知哪些項目會被重複加入。修復時 form views 的數量顯示也必須反映排除後的結果。

### 涉及 Model/Table

| Model | Table | 角色 |
|-------|-------|------|
| `Tools::ErpPeriod::Models::ErpPeriod` | `erp_periods` | 週期主表 |
| `Tools::ErpPeriod::Models::ErpRecord` | `erp_records` | 週期明細（source 與週期的關聯） |
| `ElectricityAccounting::ElectricBill::Models::ElectricBillAccount` | `electric_bill_accounts` | 電費帳戶（source） |
| `ElectricityBilling::Models::RoofRentalAccount` | `roof_rental_accounts` | 屋頂租金帳戶（source） |
| `ElectricityAccounting::PeriodicLedger::Models::DueDetail` | `due_details` | 應付明細（source） |

### 修復方向

1. **Query 層**：在三個 SourceIdsQuery 中加入排除條件，排除 `erp_records` 表中已存在對應 `source_type` + `source_id` 的記錄。具體做法：在查詢結果上加 `WHERE id NOT IN (SELECT source_id FROM erp_records WHERE source_type = '{對應 type}')`。

2. **Form Views 層**：確認頁面（form views）顯示的數量與清單必須使用排除後的 source_ids，讓用戶看到的筆數與實際加入的筆數一致。因 form views 的數量來源於 SourceIdsQuery 的回傳結果，修復 Query 層後 form views 應自動反映正確數量，但需驗證確認頁的 count 顯示邏輯是否有獨立的計算路徑。

### 風險點

- 修改查詢邏輯時需注意 `source_type` 字串必須與 `InsertRecordsToPeriod` 中定義的常數一致（如 `ElectricityAccounting::ElectricBill::Models::ElectricBillAccount`）
- `DueQuery` 的 source_type 是 `ElectricityAccounting::AccountingEntry::Models::DueDetail`（注意：controller 中的 DEFAULT_SOURCE_TYPE_MAP 定義的是 `ElectricityAccounting::PeriodicLedger::Models::DueDetail`，需確認實際使用的 source_type）
- 需確認被刪除（rejected/destroyed）的 ErpPeriod 對應的 ErpRecord 是否已被清理（`dependent: :destroy` 確認已設定）
