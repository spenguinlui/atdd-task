# 申報所得管理新增匯出申報資料功能與身分證字號欄位

> **Task ID**: 3333c5f1-af18-4d38-8cdd-61add393897e | **Type**: feature | **Project**: core_web | **Date**: 2026-04-07
> **Domain**: Crowdfund::TaxInfo | **Confidence**: 97%

## Request

在 Admin「申報所得管理」頁面（accounting/tax_infos）的批次上傳按鈕右邊，新增一個「匯出申報資料」按鈕。點擊後自動從既有資料庫拉出所有用戶與屋主的所得稅申報資料，產生 XLSX 下載。

同時，以下所有地方都要加上「身分證字號/統一編號」(identity_number) 欄位：
- tax_infos 資料庫表
- tax_info_details 資料庫表
- Admin 清單頁面顯示
- 批次上傳範例檔和 Form 解析
- 匯出的 XLSX

**補充需求（2026-04-07 追加）**：匯出 XLSX 拉取的款項發放紀錄（revenue_dues），應只取「發放成功」的。此過濾只影響匯出 XLSX，不影響「申報所得管理」清單頁面。

## SA

### 資料架構

本次功能涉及兩大資料來源，需透過 SQL JOIN 組合：

**User（一般用戶）所得**：
- `revenue_dues` WHERE `owner_type = 'User'` — 提供金額（amount）、月份資訊
- `user_profiles` WHERE `owner_type = 'User'` — 提供 `COALESCE(vat_id, id_number)` 作為身分證字號/統編
- `unchanged_contract_programs` — LEFT JOIN，有記錄=未換約=`lease_income`，無記錄=已換約=`incidental_trading_income`

**Roof::Owner（屋主）所得**：
- `roof_owner_unified_incomes`（SQL VIEW，合併 `revenue_dues` + `electricity_billing_roof_rental_accounts`）— 提供金額、月份
- `user_profiles` WHERE `owner_type = 'Roof::Owner'` — 提供 `COALESCE(vat_id, id_number)`
- 屋主的 `income_method` 固定為 `lease_income`（屋主沒有換約概念）

### Payment 狀態過濾（2026-04-07 追加）

匯出 XLSX 時，revenue_dues 只取「發放成功」的款項。

**關聯路徑**：
- `revenue_dues` → `transfer_records`（via polymorphic source: `source_type = 'Revenue::Models::Due'`, `source_id = revenue_dues.id`）
- `transfer_records` → `transfer_due_records_payments`（via `due_record_id`）
- `transfer_due_records_payments` → `transfer_payments`（via `payment_id`）
- 過濾條件：`transfer_payments.status = 'success'`

**Payment enum**：`{ pending: 'pending', failed: 'failed', success: 'success' }`

**重要區分 — roof_owner_unified_incomes VIEW 的兩個資料來源**：
- `revenue_dues`（source_type = 'Revenue::Models::Due'）：需要 Payment status 過濾，JOIN 路徑同上
- `electricity_billing_roof_rental_accounts`（source_type = 'ElectricityBilling::Models::RoofRentalAccount'）：不走 Payment 流程，不需要過濾

**實作影響**：
- 此過濾不適合修改 VIEW 本身（VIEW 被其他功能共用），應在匯出查詢的 SQL 層面處理
- User 匯出 SQL：直接在 `revenue_dues` 查詢中 JOIN `transfer_records` → `transfer_due_records_payments` → `transfer_payments` 並加 WHERE `status = 'success'`
- 屋主匯出 SQL：不能直接用 `roof_owner_unified_incomes` VIEW（因為 VIEW 沒有 Payment 過濾）。需要拆分處理：
  - `revenue_dues` 來源的屋主所得：同 User 路徑，加 Payment 過濾
  - `electricity_billing_roof_rental_accounts` 來源的屋主所得：直接取用，不過濾

**適用範圍**：僅影響匯出 XLSX。清單頁面（tax_infos）的資料來自人為審查後的批次上傳，不涉及 Payment 狀態。

### income_month 格式

民國年月格式，例如 "11301"（民國113年1月）。SQL 中使用 `EXTRACT(YEAR FROM date) - 1911` 轉換。

### 既有程式架構

```
domains/crowdfund/tax_info/
├── entities/tax_info.rb, tax_info_detail.rb
├── models/record.rb (table: tax_infos), record_detail.rb (table: tax_info_details)
├── repositories/tax_info.rb, tax_info_detail.rb
├── relations/record.rb (複雜 SQL JOIN)
├── client.rb (對外查詢介面)
├── manager.rb (顯示邏輯，5/1~7/1 時間開關)
├── listener.rb (batch upload 事件處理)
└── use_cases/
    ├── build_file.rb (產生 XLSX — 既有，從 tax_infos 讀取)
    ├── build_export_file.rb (匯出 XLSX — 本次新增)
    └── send_email.rb (寄送通知)
```

Admin controllers:
- `slices/admin/controllers/admin/accounting/tax_infos_controller.rb` — CRUD（需新增 export action）
- `slices/admin/controllers/admin/accounting/tax_info_batch_creations_controller.rb` — 批次上傳
- `slices/admin/view_models/admin/accounting/tax_infos/index.rb` — 清單頁面

### 身分證字號來源

`user_profiles` 表的 `id_number`（自然人）或 `vat_id`（法人），User model 有 `profile_identity` 方法。取值邏輯：`COALESCE(vat_id, id_number)`，優先使用統一編號，其次身分證字號。若兩者皆無，欄位留空。

### 需變更的範圍

1. **DB Migration**: `tax_infos` 和 `tax_info_details` 表各新增 `identity_number` 欄位（string, nullable）
2. **匯出功能**: 新增 export action，執行 SQL 查詢並產生 XLSX
3. **匯出 SQL 過濾**: revenue_dues 只取 Payment status = 'success' 的記錄
4. **Admin 清單頁面**: index view 新增身分證字號/統編欄位顯示
5. **批次上傳**: 範例檔新增欄位、Form 解析支援 identity_number
6. **XLSX 匯出**: 包含身分證字號/統編欄位

### 跨 Model 資料比對

匯出 SQL 需 JOIN 多張表（revenue_dues, user_profiles, unchanged_contract_programs, transfer_records, transfer_due_records_payments, transfer_payments, electricity_billing_roof_rental_accounts），涉及：
- 跨 model 的金額加總（revenue_dues 多筆 → 同一用戶同月份加總）
- 跨 model 的狀態關聯過濾（unchanged_contract_programs 存在與否決定 income_method）
- 跨 model 的狀態關聯過濾（transfer_payments.status 決定 revenue_dues 是否納入）
- SQL VIEW（roof_owner_unified_incomes）合併多來源資料

Tester 在設計 fixture 前需確認 local DB 中這些表的實際資料粒度與數量關係。

### 已知問題備註

- AC2（匯出 XLSX）：Controller 缺少 export action（已實作 route 和 use case，但漏了 controller method）— 不是 spec 層面的問題，coder 需補上
