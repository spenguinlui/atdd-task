# 申報所得管理新增匯出申報資料功能與身分證字號欄位

> 任務 ID：3333c5f1-af18-4d38-8cdd-61add393897e
> 專案：core_web
> 建立日期：2026-04-07

## Business Context

**Why**: 管理員需要一鍵匯出所有用戶與屋主的所得稅申報資料（含身分證字號/統編），供年度報稅作業使用。目前缺少匯出功能且缺少身分證字號欄位。匯出應僅包含已成功發放的款項，避免將失敗或待處理的款項計入申報。
**Who**: 後台管理員（Admin）
**Impact**: 大幅減少手動彙整申報資料的時間，提升報稅作業效率

## Domain

- **主要 Domain**：Crowdfund::TaxInfo
- **相關 Domains**：Crowdfund::Revenue, Roof::Owner, UserProfile, PaymentTransfer

## ATDD Profile

- **Type**：e2e
- **Reason**：點擊匯出按鈕後可在瀏覽器即時下載 XLSX 檔案（< 60 秒），且清單頁面欄位新增亦可即時觀察。符合 E2E 驗收條件。
- **Executor**：chrome-mcp

## Acceptance Criteria

驗收標準（業務結果導向）：

- [ ] AC1: 「申報所得管理」頁面出現「匯出申報資料」按鈕，位於「批次上傳」按鈕右側
- [ ] AC2: 點擊「匯出申報資料」按鈕後，瀏覽器下載 XLSX 檔案
- [ ] AC3: XLSX 包含「申報所得」工作表（身分證字號/統編、用戶編號、用戶類型、申報方式、所得年月、申報總額）
- [ ] AC4: XLSX 包含「申報明細」工作表（身分證字號/統編、用戶編號、用戶類型、所得年月、專案名稱、整場售電收入、案場總片數、單片收入、持有片數、本期收入）
- [ ] AC5: 兩個工作表皆包含用戶與屋主的資料
- [ ] AC6: 已換約用戶的申報方式為「一時貿易所得」，未換約用戶為「租賃所得」
- [ ] AC7: 屋主的申報方式一律為「租賃所得」
- [ ] AC8: 申報所得清單頁面新增「身分證字號/統一編號」欄位顯示
- [ ] AC9: 批次上傳範例檔包含「身分證字號/統一編號」欄位
- [ ] AC10: 批次上傳可正確匯入「身分證字號/統一編號」欄位
- [ ] AC11: 用戶未填寫身分證字號與統一編號時，欄位顯示空白不報錯
- [ ] AC12: 匯出 XLSX 僅包含發放成功的款項紀錄（發放失敗或待處理的不納入）
- [ ] AC13: 屋主的屋頂租金所得不受款項發放狀態影響，正常納入匯出
- [ ] AC14: 匯出時身分證字號/統編從 user_profiles 動態取得（統一編號優先於身分證字號），不依賴 tax_infos 表的 identity_number 欄位。僅 user_type 為 User 的記錄可 JOIN user_profiles；屋主（Roof::Owner）的身分證字號需從屋主相關資料來源取得
- [ ] AC15: 匯出支援年度篩選 — 匯出按鈕旁提供年度選擇，選擇年度後僅匯出該年度的申報資料（依 income_month 前 3 碼比對民國年）

## Scenarios

### Scenario 1: 匯出按鈕顯示於正確位置

**Given** 管理員登入後台
**When** 管理員進入「申報所得管理」頁面
**Then** 頁面應顯示「匯出申報資料」按鈕
**And** 該按鈕應位於「批次上傳」按鈕的右側

### Scenario 2: 匯出 XLSX 包含「申報所得」與「申報明細」兩個工作表

**Given** 系統中有所得申報資料
**When** 管理員點擊「匯出申報資料」按鈕
**Then** 瀏覽器下載一份 XLSX 檔案
**And** XLSX 包含「申報所得」工作表，欄位為：身分證字號/統一編號、用戶編號、用戶類型、申報方式、所得年月、申報總額
**And** XLSX 包含「申報明細」工作表，欄位為：身分證字號/統一編號、用戶編號、用戶類型、所得年月、專案名稱、整場售電收入、案場總片數、單片收入、持有片數、本期收入

### Scenario 3: 匯出用戶所得依換約狀態區分申報方式

**Given** 系統中有一般用戶 A，身分證字號為「A123456789」，有未換約紀錄（unchanged_contract_programs 有記錄）
**And** 用戶 A 在民國 113 年 1 月有所得金額 10,000 元，且該款項已成功發放
**And** 系統中有一般用戶 B，統一編號為「12345678」，無未換約紀錄（已換約）
**And** 用戶 B 在民國 113 年 2 月有所得金額 20,000 元，且該款項已成功發放
**When** 管理員點擊「匯出申報資料」按鈕
**Then**「申報所得」工作表中用戶 A：身分證字號/統編為「A123456789」，申報方式為「租賃所得」，所得年月為「11301」，申報總額為 10,000
**And**「申報所得」工作表中用戶 B：身分證字號/統編為「12345678」，申報方式為「一時貿易所得」，所得年月為「11302」，申報總額為 20,000

### Scenario 4: 匯出屋主所得一律為租賃所得

**Given** 系統中有屋主 C，身分證字號為「B987654321」
**And** 屋主 C 在民國 113 年 3 月有所得金額 15,000 元，且該款項已成功發放
**When** 管理員點擊「匯出申報資料」按鈕
**Then**「申報所得」工作表中屋主 C：身分證字號/統編為「B987654321」，申報方式為「租賃所得」，所得年月為「11303」，申報總額為 15,000

### Scenario 5: 匯出包含案場明細（申報明細工作表）

**Given** 系統中有一般用戶 A，在民國 113 年 1 月於「日光案場」持有 5 片，單片收入 200 元，本期收入 1,000 元，整場售電收入 10,000 元，案場總片數 50 片
**And** 該款項已成功發放
**When** 管理員點擊「匯出申報資料」按鈕
**Then**「申報明細」工作表中有一筆用戶 A 的資料：所得年月「11301」、專案名稱「日光案場」、整場售電收入 10,000、案場總片數 50、單片收入 200、持有片數 5、本期收入 1,000

### Scenario 6: 用戶無身分證字號與統一編號時欄位留空

**Given** 系統中有一般用戶 D，未填寫身分證字號與統一編號
**And** 用戶 D 有所得資料，且該款項已成功發放
**When** 管理員點擊「匯出申報資料」按鈕
**Then** 兩個工作表中用戶 D 的身分證字號/統編欄位為空白
**And** 匯出過程不產生錯誤

### Scenario 7: 法人優先使用統一編號

**Given** 系統中有用戶 E，同時填寫了身分證字號「C111222333」與統一編號「87654321」
**And** 用戶 E 有所得資料，且該款項已成功發放
**When** 管理員點擊「匯出申報資料」按鈕
**Then** 兩個工作表中用戶 E 的身分證字號/統編顯示為「87654321」（統一編號優先）

### Scenario 8: 申報所得清單頁面顯示身分證字號/統編欄位

**Given** 系統中有已建立的申報所得資料，其中包含身分證字號「A123456789」
**When** 管理員進入「申報所得管理」清單頁面
**Then** 清單表格中應顯示「身分證字號/統一編號」欄位
**And** 對應資料列顯示「A123456789」

### Scenario 9: 批次上傳含身分證字號/統編的資料

**Given** 管理員準備了一份包含「身分證字號/統一編號」欄位的上傳檔案
**And** 檔案中有一筆資料的身分證字號/統編為「D444555666」
**When** 管理員透過批次上傳功能上傳該檔案
**Then** 系統成功匯入資料
**And** 匯入的申報所得資料中身分證字號/統編為「D444555666」

### Scenario 10: 匯出僅包含發放成功的款項

**Given** 系統中有一般用戶 F，在民國 113 年 1 月有兩筆所得：
| 款項 | 金額 | 發放狀態 |
|------|------|----------|
| 款項甲 | 5,000 元 | 發放成功 |
| 款項乙 | 3,000 元 | 發放失敗 |
**And** 系統中有一般用戶 G，在民國 113 年 2 月有一筆所得 8,000 元，狀態為「待處理」
**When** 管理員點擊「匯出申報資料」按鈕
**Then**「申報所得」工作表中用戶 F 的申報總額為 5,000（僅計入發放成功的款項甲，不計入發放失敗的款項乙）
**And**「申報所得」工作表中不應出現用戶 G（因為沒有任何發放成功的款項）

### Scenario 11: 屋主屋頂租金所得不受發放狀態過濾影響

**Given** 系統中有屋主 H，有兩種所得來源：
| 所得來源 | 金額 | 說明 |
|----------|------|------|
| 售電收入分潤 | 10,000 元 | 透過款項發放，狀態為發放成功 |
| 屋頂租金 | 6,000 元 | 不透過款項發放流程 |
**And** 系統中有屋主 I，僅有屋頂租金所得 4,000 元（無售電收入分潤）
**When** 管理員點擊「匯出申報資料」按鈕
**Then**「申報所得」工作表中屋主 H 的申報總額為 16,000（售電分潤 10,000 + 屋頂租金 6,000）
**And**「申報所得」工作表中屋主 I 的申報總額為 4,000（僅屋頂租金）

### Scenario 12: 批次上傳範例檔包含新欄位

**Given** 管理員登入後台
**When** 管理員進入批次上傳頁面並下載範例檔
**Then** 範例檔中應包含「身分證字號/統一編號」欄位

### Scenario 13: 匯出按鈕旁有年度篩選

**Given** 管理員登入後台
**When** 管理員進入「申報所得管理」頁面
**Then** 「匯出申報資料」按鈕旁應有年度篩選元件（下拉選單或輸入欄）
**And** 年度篩選預設為當前民國年（例如民國 115 年）

### Scenario 14: 選擇年度後匯出僅包含該年度資料

**Given** 系統中有以下申報資料：
| 用戶 | 所得年月 | 申報總額 | 發放狀態 |
|------|----------|----------|----------|
| 用戶 J | 11301 | 10,000 元 | 發放成功 |
| 用戶 J | 11405 | 15,000 元 | 發放成功 |
| 用戶 K | 11302 | 8,000 元 | 發放成功 |
| 用戶 K | 11412 | 12,000 元 | 發放成功 |
**When** 管理員選擇年度為「113」
**And** 管理員點擊「匯出申報資料」按鈕
**Then** 匯出的 XLSX 僅包含 income_month 以「113」開頭的資料
**And**「申報所得」工作表中有用戶 J（所得年月 11301，申報總額 10,000）
**And**「申報所得」工作表中有用戶 K（所得年月 11302，申報總額 8,000）
**And**「申報所得」工作表中不應出現所得年月為 11405 或 11412 的資料

## Technical Notes

- 匯出 SQL 需 JOIN 多張表：revenue_dues, user_profiles, unchanged_contract_programs, transfer_records, transfer_due_records_payments, transfer_payments
- roof_owner_unified_incomes 是 SQL VIEW，合併 revenue_dues 與 electricity_billing_roof_rental_accounts
- 屋主匯出不能直接使用 roof_owner_unified_incomes VIEW（因 VIEW 無 Payment 過濾），需拆分兩個來源分別處理
- Payment 關聯路徑：revenue_dues → transfer_records (polymorphic source) → transfer_due_records_payments → transfer_payments WHERE status = 'success'
- income_month 格式為民國年月（如 "11301"），需從西元年轉換：EXTRACT(YEAR FROM date) - 1911
- identity_number 取值邏輯：**不可直接讀 tax_infos.identity_number**（該欄位幾乎無資料）。匯出時須 JOIN user_profiles，取 `COALESCE(user_profiles.vat_id, user_profiles.id_number)` 作為身分證字號/統編
- identity_number JOIN 條件限制：`tax_infos.user_type = 'User'` 時可透過 `user_profiles.user_id = tax_infos.user_id` JOIN；`user_type = 'Roof::Owner'` 時需從屋主相關表取得身分證字號（需確認 roof_owners 表結構或屋主是否也透過 user_profiles 關聯）
- 既有 use_cases/build_file.rb 可作為 XLSX 產生的參考（BUG 所在：build_export_file.rb:42 直接讀 tax_infos.identity_number）
- Controller 目前缺少 export action（route 和 use case 已存在，需補 controller method）
- 年度篩選實作：Controller 接收 year 參數，BuildExportFile 接收 year 參數後以 `income_month LIKE '{year}%'` 篩選；View 的匯出按鈕旁增加年度選擇元件

## Verification Notes

- **Test Helpers**：無特殊需求
- **Special Considerations**：匯出功能需要有足夠的測試資料（包含用戶和屋主、有無身分證字號、換約與未換約、不同 Payment 狀態），tester 需在 local DB 建立相應的 seed 資料。特別注意需建立 transfer_records + transfer_due_records_payments + transfer_payments 完整關聯鏈。年度篩選測試需準備跨年度資料（如 113 年和 114 年各有數筆）。
- **Data Boundary Check**：Required — 需確認以下 model 組合：
  - revenue_dues 與 user_profiles 的 owner_type/owner_id 關聯粒度
  - unchanged_contract_programs 與 user 的對應關係（一對一或一對多）
  - revenue_dues → transfer_records → transfer_payments 的關聯粒度：**已確認 1:1**（一筆 due 只對應一筆 payment），JOIN 不需去重
  - roof_owner_unified_incomes VIEW 的實際資料結構與金額聚合方式
  - 同一用戶同月份多筆 revenue_dues 的加總行為
  - electricity_billing_roof_rental_accounts 是否有自己的狀態欄位需要考慮
  - **user_profiles 與 tax_infos 的 JOIN 條件**：user_profiles.user_id 對應 tax_infos.user_id（僅 user_type='User' 時有效），需確認 Roof::Owner 類型的身分證取得路徑
  - **income_month 的值域與格式一致性**：確認所有 income_month 皆為 5 碼民國年月格式，LIKE 篩選不會遺漏或誤匹配
