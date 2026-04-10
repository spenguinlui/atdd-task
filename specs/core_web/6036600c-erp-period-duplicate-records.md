# ERP 週期排除已有週期的單據

> 任務 ID：6036600c-3b71-4232-bd01-6d2d1ee79ac8
> 專案：core_web
> 建立日期：2026-04-10

## Business Context

**Why**: 生產環境發現 ERP 週期建立時重複加入已屬於其他週期的電費單，導致重複建立 ERP 單據紀錄
**Who**: 財務操作人員
**Impact**: 重複的 ERP 單據會導致後續匯出、核准、開票流程出現錯誤數據

## Domain

- **主要 Domain**：Tools::ErpPeriod
- **相關 Domains**：ElectricityAccounting::ElectricBill, ElectricityBilling, ElectricityAccounting::PeriodicLedger

## ATDD Profile

- **Type**：integration
- **Reason**：此 bug 涉及 SourceIdsQuery 查詢邏輯與 ErpRecord 跨表比對，無 UI 互動，屬於後端資料查詢邏輯的修正。需要建立跨 Model 的測試資料（ErpPeriod + ErpRecord + ElectricBillAccount），適合 integration 層級的 rspec 測試。
- **Executor**：rspec

## Acceptance Criteria

驗收標準：

- [ ] ElectricityBillQuery 排除已存在於任何 ErpRecord 中的 ElectricBillAccount
- [ ] RoofRentalQuery 排除已存在於任何 ErpRecord 中的 RoofRentalAccount
- [ ] DueQuery 排除已存在於任何 ErpRecord 中的 DueDetail
- [ ] 所有 source 都已有 ErpRecord 時，Query 回傳空陣列
- [ ] InsertRecordsToPeriod 對跨週期重複的 source 不再建立 ErpRecord

## Scenarios

### Scenario 1: 電費單查詢排除已有週期的帳戶

**Given** 有 3 筆電費帳戶（ID: 101, 102, 103）符合篩選條件
**And** 帳戶 101 已存在於 ErpRecord（source_type: "ElectricityAccounting::ElectricBill::Models::ElectricBillAccount", source_id: 101）
**When** ElectricityBillQuery 以該篩選條件查詢
**Then** 回傳結果為 `[102, 103]`，不包含 `101`

### Scenario 2: 屋頂租金查詢排除已有週期的帳戶

**Given** 有 2 筆屋頂租金帳戶（ID: 201, 202）符合篩選條件
**And** 帳戶 201 已存在於 ErpRecord（source_type: "ElectricityBilling::Models::RoofRentalAccount", source_id: 201）
**When** RoofRentalQuery 以該篩選條件查詢
**Then** 回傳結果為 `[202]`，不包含 `201`

### Scenario 3: 應付明細查詢排除已有週期的明細

**Given** 有 2 筆應付明細（ID: 301, 302）符合篩選條件
**And** 明細 301 已存在於 ErpRecord（對應的 source_type 和 source_id: 301）
**When** DueQuery 以該篩選條件查詢
**Then** 回傳結果為 `[302]`，不包含 `301`

### Scenario 4: 所有單據都已有週期時回傳空陣列

**Given** 有 2 筆電費帳戶（ID: 101, 102）符合篩選條件
**And** 帳戶 101 和 102 都已存在於 ErpRecord
**When** ElectricityBillQuery 以該篩選條件查詢
**Then** 回傳結果為 `[]`（空陣列）

### Scenario 5: 被刪除的週期不影響排除邏輯

**Given** 帳戶 101 曾屬於某個 ErpPeriod，但該週期已被刪除（ErpRecord 隨 dependent: :destroy 一併刪除）
**And** 帳戶 101 不存在於任何現存的 ErpRecord 中
**When** ElectricityBillQuery 以篩選條件查詢
**Then** 回傳結果包含 `101`

### Scenario 6: display_count 也應反映排除後的數量

**Given** 有 5 筆電費單（billing 層級）符合篩選條件，展開為 8 筆電費帳戶
**And** 其中 3 筆電費帳戶已存在於 ErpRecord
**When** 呼叫 ElectricityBillQuery.call 取得 source_ids
**Then** source_ids 數量為 `5`（8 - 3）

## Technical Notes

- 修改檔案：
  - `slices/admin/controllers/admin/erp_period/source_ids_queries/electricity_bill_query.rb`
  - `slices/admin/controllers/admin/erp_period/source_ids_queries/roof_rental_query.rb`
  - `slices/admin/controllers/admin/erp_period/source_ids_queries/due_query.rb`
- 排除邏輯：在查詢結果上加 `WHERE id NOT IN (SELECT source_id FROM erp_records WHERE source_type = '...')`
- source_type 常數定義在 `InsertRecordsToPeriod` 中：
  - `ElectricityAccounting::ElectricBill::Models::ElectricBillAccount`
  - `ElectricityBilling::Models::RoofRentalAccount`
  - `ElectricityAccounting::AccountingEntry::Models::DueDetail`（注意：controller 的 DEFAULT_SOURCE_TYPE_MAP 寫的是 `ElectricityAccounting::PeriodicLedger::Models::DueDetail`，需確認哪個是正確的）

## Verification Notes

- **Test Helpers**：None
- **Special Considerations**：測試需建立完整的 ErpPeriod + ErpRecord 關聯資料，確認排除邏輯正確
- **Data Boundary Check**：Required
  - `erp_records` <-> `electric_bill_accounts`：確認 source_type 字串在 erp_records 中的實際值是否與 InsertRecordsToPeriod 的常數一致
  - `erp_records` <-> `due_details`：確認 DueDetail 的 source_type 到底是 `ElectricityAccounting::AccountingEntry::Models::DueDetail` 還是 `ElectricityAccounting::PeriodicLedger::Models::DueDetail`
