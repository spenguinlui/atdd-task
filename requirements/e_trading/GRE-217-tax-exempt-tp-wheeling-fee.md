# 澎湖免稅台電轉供費系統計稅

> **Task ID**: 248ad504-1688-4bf1-9dad-4bf1032a3e08 | **Type**: feature | **Project**: e_trading | **Date**: 2026-04-07
> **Domain**: PowerWheeling::AccountingResult | **Confidence**: 96%

## Request

轉供結果若為台電澎湖區處的，因為離島政策，所以免稅。轉供費目前皆以含稅處理，過往澎湖的轉供契約只有一份，情境單純，但現在多了一份，因為有客戶有多份轉供契約，系統算完的結果是總額，也無拆分，所以概念上AM針對這些用戶的台電轉供費需要手動計算。安排系統優化，可以處理免稅的轉供契約結果。

UI 變更：上傳轉供結果的彈窗內多加一個 CHECKBOX（免稅標記）。
後端邏輯：上傳結果建立 Entry 資料時，調整資料計算並補上稅額，使其對齊一般含稅的資料。
稅率：5%。進位規則：含稅價採用四捨五入至個位數。
稅額計算：推算含稅價後，減去未稅金額推算稅額，避免造成稅差。

## SA

### 影響範圍

**主要 Domain**: `PowerWheeling::AccountingResult` — Entry 建立、稅額計算
**相關 Domains**:
- `PowerWheeling::RawResult` — 轉供原始資料上傳（`FileHistory`、`RawResultTpWheelingFee`）
- `PowerWheeling::WheelingResult` — `client.rb` 的 `tp_wheeling_fee_without_tax` 計算也有 `/1.05`
- `PowerWheeling::ResultApplication` — 報表 `consumer_info.rb` 中 `/1.05` 公式

### 現行邏輯

1. **上傳流程**：AM 在「上傳當期轉供結果檔」彈窗上傳 xlsx → `WheelingResultFileHistoriesController#create` → 建立 `RawResult::Models::FileHistory` → 觸發 `RawResult::UseCases::BatchCreateRawResults` → 建立 `RawResultTpWheelingFee` 記錄（含 `total_wheeling_fee`）
2. **計算流程**：`CalculateConsumerTask#create_tp_wheeling_fee` 讀取 `RawResultTpWheelingFee` + `TaipowerAdjustedTpWheelingFee`（電號尾碼 C 的校正記錄），加總 `total_wheeling_fee`，假設金額含稅，執行 `/1.05` 拆出未稅，差額為稅額
3. **稅額重算排除**：`CalculateAccountingResultTax` 中 `PRICE_INCLUDE_TAX_SOURCE_TYPES = ['tp_wheeling_fee']`，不對 `tp_wheeling_fee` 重算稅額，因為轉供費稅額在 `create_tp_wheeling_fee` 已經算好
4. **Entry 欄位**：`price`（未稅單價）、`total_amount`（未稅總額）、`tax`（稅額）、`quantity`（固定 1）、`invoice_group_type`（固定 `collection_and_payment`）、`account_code`（固定 `414002`）
5. **重新上傳**：`FileHistory` 使用 `find_or_initialize_by(wheeling_month, tp_service_serial)` 覆蓋，`Entry` 使用 `find_or_initialize_by(wheeling_month, source_type, source_identifier, task_id)` 覆蓋

### 需要變更的部分

#### 1. UI — 上傳彈窗新增 checkbox
- **檔案**：`slices/admin/views/admin/power_wheeling/results_management/wheeling_result_file_histories/_form.slim`
- **變更**：在上傳區域新增「免稅上傳」checkbox
- **注意**：此 checkbox 的值需要一路傳遞到 `FileHistory` 記錄上

#### 2. Model — FileHistory 新增欄位
- **表**：`power_wheeling_result_file_histories`
- **新增欄位**：`tax_exempt`（boolean, default: false）
- **目的**：記錄此批上傳的轉供結果是否為免稅

#### 3. Form 驗證
- **檔案**：`slices/admin/view_models/admin/power_wheeling/results_management/wheeling_result_file_histories/form.rb`
- **變更**：params 新增 `optional(:tax_exempt)` 欄位

#### 4. Controller
- **檔案**：`slices/admin/controllers/admin/power_wheeling/results_management/wheeling_result_file_histories_controller.rb`
- **變更**：`create` 時將 `tax_exempt` 寫入 `FileHistory`

#### 5. 核心計算邏輯
- **檔案**：`domains/power_wheeling/accounting_result/use_cases/calculate_consumer_task.rb`
- **方法**：`create_tp_wheeling_fee`
- **現行**：`total_amount = sum(total_wheeling_fee)`，`tp_wheeling_fee_without_tax = (total_amount / 1.05).round`，`tax = total_amount - tp_wheeling_fee_without_tax`
- **變更**：需判斷對應的 `FileHistory.tax_exempt`
  - 含稅（現行）：`未稅 = (含稅金額 / 1.05).round`，`稅 = 含稅金額 - 未稅`
  - 免稅（新增）：`含稅 = (免稅金額 * 1.05).round`，`稅 = 含稅金額 - 免稅金額`，Entry 的 `price = 免稅金額`，`total_amount = 免稅金額`，`tax = 含稅 - 免稅`
  - **注意**：一個 task 可能同時有含稅和免稅的 `tp_service_serial`，需分別查 `FileHistory.tax_exempt` 後分組計算再加總

#### 6. TaipowerAdjustedTpWheelingFee 處理
- `TaipowerAdjustedTpWheelingFee` 是從 `power_wheeling_raw_result_tp_wheeling_fees` 撈電號尾碼 C 的校正記錄
- 其 `tp_service_serial` 來自同一批上傳，因此免稅屬性跟隨對應的 `FileHistory.tax_exempt`
- 計算時需用相同的 `tp_service_serial` 關聯查詢 `FileHistory.tax_exempt`

#### 7. 重新上傳覆蓋
- `FileHistory` 的 `find_or_initialize_by(wheeling_month, tp_service_serial)` 會覆蓋同月同轉供契約的記錄
- `tax_exempt` 欄位會隨 `update_attributes` 一起被覆蓋 — 符合需求（含稅傳成未稅可重傳修正）

### 本次不做（需求明確排除）

- 報表頁面的 `/1.05` 公式（`consumer_info.rb`）：需求確認目前無需特殊識別
- 發票 type 變更：維持 `collection_and_payment`
- 營業稅類型變更：維持應稅
- 會計科目變更：維持 `414002`
- 資料呈現頁面調整：與 AM & 會計確認不需調整

### WheelingResult::Client 的 `/1.05`
- `wheeling_result/client.rb` 中的 `tp_wheeling_fee_without_tax` 方法也有 `/1.05`
- 此方法被 `WheelingResult` domain 使用，用於轉供結果計算
- **評估**：此處是否也需要判斷免稅？需求說「上傳結果建立 Entry 資料時調整」，未明確涵蓋此處。根據 Jira 確認的「資料呈現頁面不需調整」，暫不變更此處。但 coder 實作時應確認此 client 的使用場景是否會因免稅而產生不一致。

### 計算案例

| 場景 | 上傳金額 | tax_exempt | 含稅金額 | 未稅金額 | 稅額 |
|------|---------|-----------|---------|---------|------|
| 一般含稅 | 105 | false | 105 | 100 | 5 |
| 澎湖免稅 | 200 | true | 210 | 200 | 10 |
| 澎湖免稅（需四捨五入） | 123 | true | 130 (=123*1.05=129.15→四捨五入→129) | 123 | 6 |

**修正**：`123 * 1.05 = 129.15`，四捨五入至個位數 = `129`，稅額 = `129 - 123 = 6`。

### 跨 Model 資料比對

本功能涉及跨 model 的資料關聯：
- `FileHistory`（`tp_service_serial`, `tax_exempt`）→ `RawResultTpWheelingFee`（`tp_service_serial`, `total_wheeling_fee`）
- `TaipowerAdjustedTpWheelingFee`（子查詢從 `power_wheeling_raw_result_tp_wheeling_fees` 撈 C 尾碼）
- 關聯鍵：`tp_service_serial` + `wheeling_month`

Tester 設計 fixture 時需確認：一個 task 可能包含多個 `tp_service_serial`（多份轉供契約），其中部分為免稅、部分為含稅的混合情境。
