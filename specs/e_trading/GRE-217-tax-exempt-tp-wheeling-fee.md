# 澎湖免稅台電轉供費系統計稅

> 任務 ID：248ad504-1688-4bf1-9dad-4bf1032a3e08
> 專案：e_trading
> 建立日期：2026-04-07

## Business Context

**Why**: 澎湖區處轉供費為免稅，但系統一律當含稅處理，導致虧損。現在澎湖有多份轉供契約，手動計算已不可行。
**Who**: AM（業務人員），上傳轉供結果
**Impact**: 正確計算澎湖免稅轉供費的含稅價與稅額，消除虧損，減少手動作業

## Domain

- **主要 Domain**：PowerWheeling::AccountingResult
- **相關 Domains**：PowerWheeling::RawResult, PowerWheeling::WheelingResult, PowerWheeling::ResultApplication

## ATDD Profile

- **Type**：integration + e2e
- **Reason**：Integration 測試已通過（13 個場景），驗證計算邏輯正確。E2E 測試補充驗證上傳流程與 UI 互動，確保 checkbox 值正確傳遞到後端並反映在結算品項。
- **Executor**：rspec（integration）、chrome-mcp（e2e）

## Acceptance Criteria

驗收標準（業務結果導向）：

- [x] AC1: 上傳轉供結果的彈窗出現「免稅」checkbox，預設未勾選
- [x] AC2: 未勾選免稅時，計算邏輯與現行完全一致（含稅金額 / 1.05 = 未稅）
- [x] AC3: 勾選免稅時，系統以免稅金額 * 1.05 推算含稅價（四捨五入至個位數），稅額 = 含稅價 - 免稅金額
- [x] AC4: Entry 資料的 price、total_amount 為未稅金額，tax 為稅額，invoice_group_type 為 collection_and_payment
- [x] AC5: 一個 task 含混合情境（部分含稅、部分免稅的 tp_service_serial）時，分別計算後加總正確
- [x] AC6: 重新上傳時，免稅狀態隨之覆蓋（可修正上傳錯誤）
- [x] AC7: TaipowerAdjustedTpWheelingFee（C 尾碼校正記錄）遵循同一 tp_service_serial 的免稅設定

## Scenarios（Integration — 已通過）

### Scenario 1: 一般含稅上傳（現行邏輯不變）

**Given** 一筆轉供結果已上傳，tp_service_serial 為 TS001，tax_exempt 為 false
**And** RawResultTpWheelingFee 記錄的 total_wheeling_fee 加總為 105
**When** CalculateConsumerTask 執行 create_tp_wheeling_fee
**Then** Entry 的 total_amount 應為 100（= 105 / 1.05 四捨五入）
**And** Entry 的 tax 應為 5（= 105 - 100）
**And** Entry 的 price 應為 100
**And** Entry 的 invoice_group_type 應為 collection_and_payment

### Scenario 2: 澎湖免稅上傳

**Given** 一筆轉供結果已上傳，tp_service_serial 為 TS002，tax_exempt 為 true
**And** RawResultTpWheelingFee 記錄的 total_wheeling_fee 加總為 200
**When** CalculateConsumerTask 執行 create_tp_wheeling_fee
**Then** Entry 的 total_amount 應為 200（未稅金額不變）
**And** Entry 的 tax 應為 10（= 200 * 1.05 四捨五入 210 - 200）
**And** Entry 的 price 應為 200

### Scenario 3: 免稅金額需四捨五入

**Given** 一筆轉供結果已上傳，tp_service_serial 為 TS003，tax_exempt 為 true
**And** RawResultTpWheelingFee 記錄的 total_wheeling_fee 加總為 123
**When** CalculateConsumerTask 執行 create_tp_wheeling_fee
**Then** 含稅金額為 129（= 123 * 1.05 = 129.15 四捨五入）
**And** Entry 的 total_amount 應為 123
**And** Entry 的 tax 應為 6（= 129 - 123）

### Scenario 4: 混合情境 — 同一 task 含含稅和免稅的 tp_service_serial

**Given** task 包含兩個 tp_service_serial 的轉供記錄
**And** TS001 的 tax_exempt 為 false，total_wheeling_fee 加總為 105
**And** TS002 的 tax_exempt 為 true，total_wheeling_fee 加總為 200
**When** CalculateConsumerTask 執行 create_tp_wheeling_fee
**Then** TS001 部分：未稅 = 100（105/1.05），稅 = 5
**And** TS002 部分：未稅 = 200，稅 = 10（210-200）
**And** Entry 的 total_amount 應為 300（100 + 200）
**And** Entry 的 tax 應為 15（5 + 10）

### Scenario 5: TaipowerAdjustedTpWheelingFee 遵循免稅設定

**Given** 一筆轉供結果已上傳，tp_service_serial 為 TS002，tax_exempt 為 true
**And** RawResultTpWheelingFee 有一般記錄 total_wheeling_fee = 150
**And** TaipowerAdjustedTpWheelingFee（C 尾碼校正）有記錄 total_wheeling_fee = 50
**When** CalculateConsumerTask 執行 create_tp_wheeling_fee
**Then** 加總免稅金額為 200（150 + 50）
**And** 含稅金額為 210（200 * 1.05 四捨五入）
**And** Entry 的 total_amount 應為 200
**And** Entry 的 tax 應為 10

### Scenario 6: 重新上傳覆蓋免稅狀態

**Given** 已上傳 TS002 的轉供結果，tax_exempt 為 true
**And** 系統已產生免稅計算的 Entry
**When** AM 重新上傳 TS002 的轉供結果，這次 tax_exempt 為 false
**And** CalculateConsumerTask 重新執行
**Then** FileHistory 的 tax_exempt 應被覆蓋為 false
**And** Entry 應以含稅邏輯重新計算

### Scenario 7: 免稅 checkbox 預設未勾選

**Given** AM 進入「上傳當期轉供結果檔」頁面
**When** 彈窗載入完成
**Then** 免稅 checkbox 應為未勾選狀態（預設含稅）

## Scenarios（E2E — 待建立）

### E2E 流程概覽

**上傳頁面**：`/admin/power_wheeling/results_management/wheeling_result_file_histories/new`
- 此頁面為 popup 視窗，從「轉供結果檔案管理」列表頁觸發
- 列表頁 URL：`/admin/power_wheeling/results_management/wheeling_result_file_histories`

**上傳表單欄位**：
1. 台電單據製發日期（datepicker）
2. 檔案上傳（xls/xlsx，支援多檔）
3. 免稅上傳（checkbox，預設未勾選）— 本次新增
4. 確定按鈕

**上傳 xlsx 檔案格式**：台電轉供結果標準格式
- B2 儲存格：`電能轉/直供服務編號：{tp_service_serial}`（如 `電能轉/直供服務編號：TS002`）
- G2 儲存格：`帳單年月：{year}/{month}`（如 `帳單年月：2026/04`）
- 第 3 行起為資料列，欄位對應：發電電號、發電表號、用戶電號、用戶表號、月服務使用量(kWh)、輸電費率、配電費率、電力調度費率、輔助服務費率、費用

**上傳後處理流程**：
1. Controller 解析 xlsx metadata（tp_service_serial、wheeling_month）
2. 建立/更新 `FileHistory` 記錄（含 `tax_exempt` 欄位）
3. 觸發 Sidekiq 非同步事件鏈：
   - `BatchCreateRawResults`（建立 RawResult + RawResultTpWheelingFee）
   - `RawResultCreated`（驗證系統資訊、建立校正任務、初始化進度）
   - 後續：WheelingResult 計算 -> BillingResult -> `CalculateConsumerTask`（建立 Entry）
4. 完成後顯示「檔案上傳成功，請到 Slack 查看資料建立訊息」

**驗證頁面**：`/admin/power_wheeling/calculation_management/accounting_entries`
- 頁面標題：「結算品項管理」
- 可用篩選：週期月份、電費所屬方案、所屬企業
- 顯示欄位：電費類型、週期月份、項目節點、合約編號、合約別名、電費所屬方案、名目、單價、數量、稅額、合計

### E2E Scenario 1: 免稅上傳 — checkbox 出現且可勾選

**前置條件**：
- 已登入 admin 帳號，有 `power_wheeling` 權限
- 有一個有效的澎湖區處轉供契約（tp_service_serial 對應的 TaipowerContract 存在且時間區間涵蓋測試月份）

**Given** AM 已登入後台
**When** AM 進入「轉供結果檔案管理」頁面（`/admin/power_wheeling/results_management/wheeling_result_file_histories`）
**And** 點擊「新增」按鈕（popup-window）
**Then** popup 彈窗應顯示「上傳當期轉供結果檔」
**And** 表單應包含「免稅上傳」checkbox
**And** checkbox 預設為未勾選

### E2E Scenario 2: 免稅上傳後結算品項正確

**前置條件**：
- 已登入 admin 帳號
- 有一個有效的澎湖區處轉供契約（如 tp_service_serial = `PH001`）
- 該轉供契約的用戶有對應的 account，且已設定 tp_wheeling_fee 為外加費用
- 已建立當月的 task（after_wheeling 類型）
- 準備測試用 xlsx 檔案：
  - B2 = `電能轉/直供服務編號：PH001`
  - G2 = `帳單年月：{測試年}/{測試月}`
  - 資料列含至少一筆 total_wheeling_fee = 200 的記錄

**Given** AM 已登入後台
**And** 測試用 xlsx 檔案已準備好
**When** AM 進入上傳彈窗
**And** 上傳 xlsx 檔案
**And** 勾選「免稅上傳」checkbox
**And** 點擊「確定」
**Then** 頁面應顯示「檔案上傳成功，請到 Slack 查看資料建立訊息」

**When** 等待 Sidekiq 非同步處理完成（事件鏈：BatchCreateRawResults -> RawResultCreated -> ... -> CalculateConsumerTask）
**And** AM 進入「結算品項管理」頁面（`/admin/power_wheeling/calculation_management/accounting_entries`）
**And** 篩選週期月份 = 測試月份
**Then** 應可找到 source_type 為 tp_wheeling_fee 的結算品項
**And** 該品項的「單價」（price）應為 200（未稅金額）
**And** 該品項的「稅額」（tax）應為 10（= 200 * 1.05 四捨五入 210 - 200）
**And** 該品項的「合計」（total_amount）應為 200

### E2E Scenario 3: 未勾選免稅上傳（含稅，現行邏輯）

**前置條件**：同 E2E Scenario 2，但使用一般含稅的轉供契約

**Given** AM 已登入後台
**And** 測試用 xlsx 檔案已準備好（total_wheeling_fee = 105）
**When** AM 進入上傳彈窗
**And** 上傳 xlsx 檔案
**And** 不勾選「免稅上傳」（維持預設）
**And** 點擊「確定」
**Then** 頁面應顯示上傳成功訊息

**When** 等待非同步處理完成
**And** AM 進入「結算品項管理」頁面篩選對應月份
**Then** tp_wheeling_fee 品項的「單價」應為 100（= 105 / 1.05 四捨五入）
**And** 「稅額」應為 5（= 105 - 100）
**And** 「合計」應為 100

### E2E Scenario 4: 重新上傳修正免稅狀態

**前置條件**：E2E Scenario 2 已執行完畢（免稅上傳已產生結算品項）

**Given** 系統已有 PH001 的免稅上傳結果及對應結算品項
**When** AM 再次進入上傳彈窗
**And** 上傳同一份 xlsx 檔案（同一 tp_service_serial + wheeling_month）
**And** 這次不勾選「免稅上傳」
**And** 點擊「確定」
**Then** 頁面應顯示上傳成功訊息

**When** 等待非同步處理完成
**And** AM 進入「結算品項管理」頁面篩選對應月份
**Then** tp_wheeling_fee 品項的計算結果應以含稅邏輯更新
**And** 若原上傳金額為 200：單價應為 190（= 200 / 1.05 四捨五入），稅額應為 10

## E2E 測試資料需求

### 帳號與權限
- admin 帳號，具備 `power_wheeling` 與 `accounting_details` 權限

### 轉供契約
- 至少一個有效的 TaipowerContract，tp_service_serial 對應測試 xlsx 中的編號
- TaipowerContract 的 `start_wheeling_date` <= 測試月份 <= `end_wheeling_date`

### 帳戶設定
- 對應的 Account 已設定 `tp_wheeling_fee` 為外加費用（externalized_fee）
- Account 有對應的 CppaContract、Plan、電號對應

### 進度管理
- 當月已建立 Task（task_type: after_wheeling, calculation_mode: systematic）

### xlsx 測試檔案
- 需製作符合台電標準格式的 xlsx：
  - B2：`電能轉/直供服務編號：{tp_service_serial}`
  - G2：`帳單年月：{year}/{month}`
  - 第 3 行起：發電電號、發電表號、用戶電號、用戶表號、月服務使用量、輸電費率、配電費率、電力調度費率、輔助服務費率、費用（total_wheeling_fee）

### Sidekiq 處理
- E2E 測試需等待完整的非同步事件鏈完成
- 事件鏈：上傳 -> BatchCreateRawResults -> RawResultCreated -> WheelingResult 處理 -> BillingResult -> CalculateConsumerTask
- 預估處理時間：視系統負載，可能需要 10-30 秒
- 驗證策略：輪詢「結算品項管理」頁面直到出現對應記錄，或檢查 Task 狀態變為 calculation_completed

## Technical Notes

- `FileHistory` 需新增 `tax_exempt` boolean 欄位（需 migration）— 已完成
- `create_tp_wheeling_fee` 需根據 `tp_service_serial` 反查 `FileHistory.tax_exempt` — 已完成
- `TaipowerAdjustedTpWheelingFee` 的 SQL 子查詢含 `tp_service_serial`，可用於關聯查詢免稅屬性
- `CalculateAccountingResultTax` 的 `PRICE_INCLUDE_TAX_SOURCE_TYPES` 排除邏輯不需修改，因為 `tp_wheeling_fee` 的稅額仍在 `create_tp_wheeling_fee` 中完成計算
- 一個 task 可能跨多個 `tp_service_serial`，需分組計算含稅/免稅後再合併寫入 Entry
- `WheelingResult::Client` 和 `ResultApplication::ConsumerInfo` 中的 `/1.05` 本次暫不調整（需求確認報表不需變更），但 coder 應評估是否有不一致風險
- Controller `create` 中使用 `find_or_initialize_by(wheeling_month, tp_service_serial)` 覆蓋機制確保重新上傳可修正 tax_exempt 狀態

## Verification Notes

- **Test Helpers**：async（`perform_enqueued_jobs` 或直接呼叫 UseCase）for integration；Sidekiq 輪詢 for E2E
- **Special Considerations**：混合情境（同一 task 含含稅和免稅）是關鍵邊界測試；E2E 需等待完整非同步鏈完成
- **Data Boundary Check**：Required — `FileHistory`（`tp_service_serial`, `tax_exempt`）與 `RawResultTpWheelingFee`（`tp_service_serial`, `total_wheeling_fee`）之間的關聯。需確認一個 task 實際上可能包含多少個 tp_service_serial，以及 C 尾碼校正記錄的數量比例。
