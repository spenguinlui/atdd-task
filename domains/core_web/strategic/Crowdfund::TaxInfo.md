# Crowdfund::TaxInfo -- 商務邏輯

> **Domain**: Crowdfund::TaxInfo
> **Project**: core_web
> **Last Updated**: 2026-04-07

## 商務目的
管理群眾集資平台的所得稅申報資料。負責彙整平台上各類付款所產生的所得資訊，轉換為符合政府稅務系統格式的申報資料，供財務團隊進行年度所得申報作業。

## 商務能力
- 批次上傳所得申報資料
- 匯出 XLSX 格式的所得申報檔案（含過濾條件）
- 所得資料清單管理與查詢

## 範疇定義
**包含**:
- 所得稅申報資料的建立、查詢、匯出
- 所得類別（IncomeMethod）的判定邏輯
- 身分識別碼（IdentityNumber）的解析
- 所得月份（IncomeMonth）的民國年轉換
- 屋主租賃所得的特殊處理邏輯

**不包含**:
- 付款流程本身（屬於 PaymentTransfer 上游）
- 營收計算（屬於 Revenue 上游）
- 用戶身份管理（屬於 UserProfile 上游）
- 屋主資格認定（屬於 Roof::Owner 上游）
- 電費帳單計算（屬於 ElectricityBilling 上游）

## 核心概念
參見 `domains/core_web/ul.md`：
- **TaxInfo**: 所得稅申報資料的聚合根，管理整體申報流程
- **TaxInfoDetail**: 單筆所得明細，記錄所得人、金額、類別等
- **Due**: 應付款項，所得計算的基礎資料來源
- **Payment**: 付款記錄，success 狀態為匯出過濾條件
- **IncomeMethod**: 所得類別，區分租賃所得與其他所得
- **IdentityNumber**: 身分識別碼，COALESCE(vat_id, id_number)
- **IncomeMonth**: 民國年月格式的所得月份

## 商務規則
本 Domain 的規則記錄於 `domains/core_web/business-rules.md`：
- CA-001: IncomeMethod Determination -- 所得類別判定
- CA-002: IdentityNumber Resolution -- 身分識別碼解析
- CA-003: IncomeMonth Conversion -- 所得月份民國年轉換
- CR-001: Export Payment Status Filter -- 匯出僅取 success
- CR-002: RoofRental Bypass Payment Filter -- 屋頂租賃不受過濾
- CR-003: Due-Payment Cardinality -- success 下等效 1:1

## 商務依賴
### 我們需要的資訊（上游）
| 來源 Domain | 提供什麼商務資訊 | 商務關係 |
|-------------|-----------------|---------|
| Revenue | 營收與應付款項資料（Due） | 所得金額的資料來源 |
| PaymentTransfer | 付款執行結果（Payment status） | 過濾成功付款用於匯出 |
| UserProfile | 用戶身份資訊（vat_id, id_number） | 所得人身分識別 |
| ElectricityBilling | 電費帳單相關所得資料 | 屋主租賃所得來源之一 |
| Roof::Owner | 屋主身份與租賃帳戶資訊 | 判定 IncomeMethod 為 lease_income |

### 依賴我們的（下游）
| 消費 Domain | 使用什麼商務資訊 | 商務關係 |
|-------------|-----------------|---------|
| （目前無已知下游） | - | - |

## 常見問題
### Q: 匯出和清單功能有什麼差異？
**A**: 清單功能顯示所有所得資料，不做額外過濾；匯出功能則會套用 CR-001 過濾條件（僅取 payment status = success 的記錄），並且 RoofRentalAccount 依 CR-002 繞過此過濾。兩者是同一份資料的不同查詢視角。

### Q: 屋主為什麼會有兩種所得來源？
**A**: 屋主出租屋頂安裝太陽能板會產生租賃所得（lease_income），這部分透過 RoofRentalAccount 管理。同時，屋主若以一般用戶身份參與群眾集資，也可能產生其他類型的所得（OtherIncome）。RoofOwnerUnifiedIncomes 將這兩種所得統整歸戶，方便年度申報。

## Change History
| Date | Change | Changed By | Reason |
|------|--------|------------|--------|
| 2026-04-07 | Initial strategic document created | curator | Knowledge audit for Crowdfund::TaxInfo domain |
