# Feature: 統一屋頂租金生命週期追蹤

> 任務 ID: cc4cbf40-2330-41ea-af0f-30f209a968f8
> 專案: core_web
> 建立日期: 2026-04-07

## Business Context

**Why**: 屋主租金來源分散在兩個 Model（Revenue::Models::Due、ElectricityBilling::Models::RoofRentalAccount），需要統一追蹤，且現行部署的 DB VIEW 與原始碼定義不一致，會導致頁面 500 error。
**Who**: Admin 後台使用者（財務人員）、系統自動化流程（批次上傳、回填）
**Impact**: 修復 VIEW 不一致問題、啟用屋主應發金額列表頁、建立 source 自動配對與歷史回填機制

## Domain

- **主要 Domain**: PaymentTransfer
- **相關 Domains**: Revenue（Due）、ElectricityBilling（RoofRentalAccount、ElectricBill）

## ATDD Profile

- **Type**: Mixed（Integration + E2E）
- **Reason**: VIEW SQL 正確性、配對邏輯、回填邏輯適合 Integration 測試；Admin 頁面載入及欄位顯示需要 E2E 測試
- **Executor**: Integration = rspec, E2E = chrome-mcp

## Acceptance Criteria

- [ ] AC1: DB VIEW `roof_owner_unified_incomes` 包含 `source_id` 欄位，且 `id` 由 ROW_NUMBER 產生，不會跨來源重複
- [ ] AC2: VIEW 正確聚合 Revenue::Models::Due（owner_type='Roof::Owner'）和 ElectricityBilling::Models::RoofRentalAccount 兩種來源
- [ ] AC3: Admin「屋主應發金額」頁面正常載入，不出現 500 error
- [ ] AC4: 列表正確顯示電號、所有人名稱、案場名稱、週期名稱、計費期間、發放金額、來源類型
- [ ] AC5: source_record 反查能正確取得原始 Due 或 RoofRentalAccount 記錄
- [ ] AC6: 案場搜尋（project_id_eq）功能正常過濾結果
- [ ] AC7: Info Widgets 顯示正確的資料筆數和總金額
- [ ] AC8: BatchUploadDueRecords::AutoMatchSource 上傳屋主 DueRecord 時自動配對 RoofRentalAccount
- [ ] AC9: BackfillDueRecordSources 正確回填歷史 source 為 nil 的 DueRecord，配對失敗時不中斷並輸出 CSV
- [ ] AC10: RoofRentalAccountMatcher 以 roof_owner_id + payment_date 查詢候選，金額相符者優先，多筆時取最小 id

## Scenarios

---

### Part A: VIEW SQL 正確性（Integration）

### Scenario 1: VIEW 結構包含 source_id 和合成 id

**Given** 資料庫已執行 `CreateRoofOwnerUnifiedIncomes` migration（使用 v01.sql）
**When** 查詢 `roof_owner_unified_incomes` VIEW 的欄位結構
**Then** 應包含欄位：`id`、`source_id`、`source_type`、`project_id`、`roof_owner_id`、`amount`、`payment_date`、`created_at`、`updated_at`
**And** `id` 應為 ROW_NUMBER 合成值（連續整數）
**And** `source_id` 應為原始 table 的 id

- **信心度**: 98%
- **來源**: v01.sql 原始碼 vs schema.rb 差異分析

### Scenario 2: 兩種來源正確聚合且 id 不重複

**Given** 存在 2 筆 Revenue::Models::Due（owner_type='Roof::Owner'，id=1, id=2）
**And** 存在 2 筆 ElectricityBilling::Models::RoofRentalAccount（id=1, id=3）
**When** 查詢 RoofOwnerUnifiedIncome.all
**Then** 應回傳 4 筆記錄
**And** 4 筆的 `id` 應各不相同（1, 2, 3, 4）
**And** source_type 為 'Revenue::Models::Due' 的記錄有 2 筆
**And** source_type 為 'ElectricityBilling::Models::RoofRentalAccount' 的記錄有 2 筆

- **信心度**: 98%
- **來源**: v01.sql UNION ALL 結構

### Scenario 3: source_record 反查成功

**Given** VIEW 中有一筆 source_type='Revenue::Models::Due'、source_id=42 的記錄
**And** Revenue::Models::Due 中存在 id=42 的記錄
**When** 呼叫該 VIEW 記錄的 `source_record` 方法
**Then** 應回傳 Revenue::Models::Due id=42 的實體

- **信心度**: 98%
- **來源**: model source_record 方法定義

### Scenario 4: source_record 對不存在的來源回傳 nil

**Given** VIEW 中有一筆 source_type='Revenue::Models::Due'、source_id=999
**And** Revenue::Models::Due 中不存在 id=999
**When** 呼叫該 VIEW 記錄的 `source_record` 方法
**Then** 應回傳 nil（不拋出例外）

- **信心度**: 98%
- **來源**: model source_record 使用 find_by

### Scenario 5: payment_date 排序（DESC）

**Given** VIEW 中有 payment_date 分別為 2026-01-01、2026-03-15、2026-02-10 的記錄
**When** 查詢 VIEW 的 id 順序
**Then** id=1 對應 payment_date 2026-03-15（最新）
**And** id=2 對應 payment_date 2026-02-10
**And** id=3 對應 payment_date 2026-01-01（最舊）

- **信心度**: 95%
- **來源**: v01.sql ROW_NUMBER() OVER (ORDER BY payment_date DESC NULLS LAST, ...)

---

### Part B: Admin 頁面 — 屋主應發金額（E2E）

### Scenario 6: 頁面正常載入

**Given** 資料庫中存在至少 1 筆 Due（owner_type='Roof::Owner'）和 1 筆 RoofRentalAccount
**And** 使用者已登入 Admin 後台
**When** 瀏覽「屋主應發金額」頁面（路徑：electricity_accounting/ledger_management/roof_owner_individual_incomes）
**Then** 頁面應正常載入（HTTP 200）
**And** 頁面標題顯示「屋主應發金額」
**And** 列表應顯示資料

- **信心度**: 95%
- **來源**: ViewModel Index 類定義 + schema.rb vs v01.sql 不一致為關鍵風險

### Scenario 7: 列表欄位正確顯示 — Due 來源

**Given** 存在 1 筆 Due 來源的記錄，關聯案場「陽光一號」、電號「12-34-5678-90」、週期名「2026年03月」
**When** 頁面載入完成
**Then** 該筆記錄應顯示：
  - 電號：12-34-5678-90
  - 案場名稱：陽光一號
  - 來源類型：Revenue::Models::Due
  - 發放金額：正確數字

- **信心度**: 90%
- **來源**: ViewModel decorate_due_item 邏輯推導，電號取自 due.bill.ppa.electric_number

### Scenario 8: 列表欄位正確顯示 — RoofRentalAccount 來源

**Given** 存在 1 筆 RoofRentalAccount 來源的記錄，關聯案場「陽光二號」、計費期間 2026/01/01 - 2026/01/31
**When** 頁面載入完成
**Then** 該筆記錄應顯示：
  - 案場名稱：陽光二號
  - 計費期間：2026/01/01 - 2026/01/31
  - 來源類型：ElectricityBilling::Models::RoofRentalAccount

- **信心度**: 90%
- **來源**: ViewModel decorate_rra_item 邏輯推導

### Scenario 9: 案場搜尋功能

**Given** 列表中有來自案場 A（project_id=10）和案場 B（project_id=20）的記錄
**When** 使用者在搜尋欄選擇案場 A 並送出
**Then** 列表應只顯示案場 A 的記錄
**And** 案場 B 的記錄不應出現

- **信心度**: 95%
- **來源**: Ransack project_id_eq filter

### Scenario 10: Info Widgets 正確顯示

**Given** 列表中有 3 筆記錄，金額分別為 1000、2000、3000
**When** 頁面載入完成
**Then** 「資料筆數」Widget 顯示 3 筆
**And** 「總金額」Widget 顯示 6,000 元

- **信心度**: 95%
- **來源**: ViewModel info_widgets 定義

### Scenario 11: 下載特殊調整格式示範檔

**Given** 使用者在「屋主應發金額」頁面
**When** 點擊「下載特殊調整格式示範檔」
**Then** 應下載檔案（不報錯）

- **信心度**: 90%
- **來源**: action_items 定義

---

### Part C: Source 自動配對（Integration）

### Scenario 12: AutoMatchSource — 配對成功

**Given** 存在 RoofRentalAccount（roof_owner_id=5, payment_date='2026-03-01', amount=1500）
**When** 呼叫 AutoMatchSource.call 傳入 benificiary_type='Roof::Owner', benificiary_id=5, registered_at='2026-03-01', amount=1500
**Then** 回傳的 DueRecord 應有 source_type='ElectricityBilling::Models::RoofRentalAccount'
**And** source_id 應等於該 RoofRentalAccount 的 id

- **信心度**: 98%
- **來源**: auto_match_source.rb 程式碼

### Scenario 13: AutoMatchSource — 非屋主類型不配對

**Given** 存在 RoofRentalAccount（roof_owner_id=5, payment_date='2026-03-01'）
**When** 呼叫 AutoMatchSource.call 傳入 benificiary_type='User'（非 Roof::Owner）
**Then** 回傳的 DueRecord 不應有自動配對的 source_type 和 source_id

- **信心度**: 98%
- **來源**: auto_match_source.rb 條件判斷

### Scenario 14: RoofRentalAccountMatcher — 金額相符者優先

**Given** 存在 2 筆 RoofRentalAccount：
  - id=10, roof_owner_id=5, payment_date='2026-03-01', amount=1000
  - id=11, roof_owner_id=5, payment_date='2026-03-01', amount=2000
**When** 呼叫 find_matching_rra(roof_owner_id: 5, payment_date: '2026-03-01', amount: 2000)
**Then** 應回傳 id=11 的 RoofRentalAccount（金額相符）

- **信心度**: 98%
- **來源**: matcher 的 select + amount 比對邏輯

### Scenario 15: RoofRentalAccountMatcher — 無金額相符取最小 id

**Given** 存在 2 筆 RoofRentalAccount：
  - id=10, roof_owner_id=5, payment_date='2026-03-01', amount=1000
  - id=11, roof_owner_id=5, payment_date='2026-03-01', amount=2000
**When** 呼叫 find_matching_rra(roof_owner_id: 5, payment_date: '2026-03-01', amount: 9999)
**Then** 應回傳 id=10（order(:id) 的第一筆）

- **信心度**: 98%
- **來源**: matcher fallback 到 candidates.first

### Scenario 16: RoofRentalAccountMatcher — 無候選回傳 nil

**Given** 不存在 roof_owner_id=5, payment_date='2026-03-01' 的 RoofRentalAccount
**When** 呼叫 find_matching_rra(roof_owner_id: 5, payment_date: '2026-03-01', amount: 1000)
**Then** 應回傳 nil

- **信心度**: 98%
- **來源**: matcher 的 return nil if candidates.size == 0

---

### Part D: 歷史回填（Integration）

### Scenario 17: BackfillDueRecordSources — 成功回填

**Given** 存在 DueRecord（benificiary_type='Roof::Owner', benificiary_id=5, source_type=nil, registered_at='2026-03-01', amount=1500）
**And** 存在 RoofRentalAccount（roof_owner_id=5, payment_date='2026-03-01', amount=1500）
**When** 呼叫 BackfillDueRecordSources.call
**Then** 該 DueRecord 的 source_type 應更新為 'ElectricityBilling::Models::RoofRentalAccount'
**And** source_id 應更新為該 RoofRentalAccount 的 id
**And** Result.matched_count 應為 1

- **信心度**: 98%
- **來源**: backfill_due_record_sources.rb 程式碼

### Scenario 18: BackfillDueRecordSources — source_type='manual' 也列入回填

**Given** 存在 DueRecord（benificiary_type='Roof::Owner', source_type='manual'）
**And** 存在匹配的 RoofRentalAccount
**When** 呼叫 BackfillDueRecordSources.call
**Then** 該 DueRecord 應被回填（source_type='manual' 包含在查詢條件 `[nil, 'manual']` 中）

- **信心度**: 98%
- **來源**: backfill where 條件

### Scenario 19: BackfillDueRecordSources — 配對失敗不中斷

**Given** 存在 3 筆待回填的 DueRecord
**And** 第 1 筆有匹配的 RoofRentalAccount
**And** 第 2 筆無匹配
**And** 第 3 筆有匹配的 RoofRentalAccount
**When** 呼叫 BackfillDueRecordSources.call
**Then** Result.matched_count 應為 2
**And** Result.unmatched_count 應為 1
**And** 第 2 筆不影響第 3 筆的回填

- **信心度**: 98%
- **來源**: find_each + begin/rescue 結構

### Scenario 20: BackfillDueRecordSources — 未匹配記錄輸出 CSV

**Given** 回填過程有 1 筆未匹配的 DueRecord
**When** BackfillDueRecordSources.call 完成
**Then** Result.csv_path 應指向 tmp/unmatched_due_records.csv
**And** CSV 內容應包含 due_record_id、roof_owner_id、owner_name、amount、payment_date

- **信心度**: 98%
- **來源**: write_csv 方法定義

### Scenario 21: BackfillDueRecordSources — 更新失敗時 rescue 不中斷

**Given** 存在待回填 DueRecord，但更新時發生 ActiveRecord::RecordInvalid
**When** 呼叫 BackfillDueRecordSources.call
**Then** 該筆被歸入 unmatched_records
**And** 後續記錄仍繼續處理

- **信心度**: 95%
- **來源**: rescue ActiveRecord::RecordInvalid, StandardError

---

### Part E: 邊界與一致性（Integration）

### Scenario 22: VIEW 與 schema.rb 一致性（關鍵修復驗證）

**Given** migration 20260403000000 已執行
**When** 執行 `rails db:migrate` 後檢查 schema.rb
**Then** schema.rb 中 `roof_owner_unified_incomes` 的 SQL 定義應包含 `ROW_NUMBER()`
**And** 應包含 `source_id` 欄位
**And** 不應直接使用原始 table 的 `id` 作為 VIEW 的 `id`

- **信心度**: 98%
- **來源**: schema.rb vs v01.sql 差異為本次修復的核心問題

### Scenario 23: VIEW readonly 保護

**Given** 一筆 RoofOwnerUnifiedIncome 記錄
**When** 嘗試呼叫 save 或 update
**Then** 應拋出 ActiveRecord::ReadOnlyRecord 錯誤

- **信心度**: 98%
- **來源**: model readonly? 方法

## Technical Notes

1. **核心問題**：schema.rb（已部署）的 VIEW 定義缺少 `source_id` 和 `ROW_NUMBER()`，與 v01.sql 不一致。Migration 尚未執行，執行後 VIEW 將更新為 v01.sql 版本。
2. **scenic gem**：使用 `scenic` gem 管理 DB VIEW，`create_view` 會讀取 `db/views/` 下的 SQL 檔案。
3. **id 衝突風險**：未修復前，UNION ALL 的兩表可能有相同 id（例如 Due id=1 和 RRA id=1），導致 ActiveRecord 混淆。
4. **N+1 已處理**：ViewModel 的 `decorate_collection` 已做批次預載（dues_map, rras_map, profiles_map），不需要額外處理。
5. **RoofRentalAccountMatcher** 查詢使用 `roof_owner_id + payment_date` 組合，已有 index migration（20260402000000）。

## Verification Notes

- **Test Helpers**: 需要 factory 建立 Revenue::Models::Due（with owner_type='Roof::Owner'）和 ElectricityBilling::Models::RoofRentalAccount
- **Special Considerations**: E2E 測試必須在 migration 執行後進行，否則 source_id 欄位不存在會導致所有頁面測試失敗
- **Data Boundary Check**: Required
  - Due.id vs RoofRentalAccount.id：確認實際環境中是否存在 id 重疊（VIEW 修復前的核心風險）
  - Due.period_date vs RoofRentalAccount.payment_date：確認日期粒度是否一致（都是 date 型別，但 Due 有 COALESCE fallback 到 created_at::date）
  - DueRecord.source_type/source_id vs RoofRentalAccount.id：回填時的配對關係
