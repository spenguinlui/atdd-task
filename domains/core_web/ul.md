# core_web Ubiquitous Language (專有名詞表)

> **Purpose**: Define the Ubiquitous Language used across core_web. This includes domain terminology, verbs (actions), states, and their semantic relationships to ensure consistent understanding among team members and AI agents.

**Last Updated**: 2026-04-07
**Maintained By**: Development Team + atdd-knowledge-curator

---

## How to Use This Glossary

- **For Developers**: Reference when encountering unfamiliar domain terms
- **For AI Agents**: Load before working on domain-specific tasks
- **For Updates**: Use atdd-knowledge-curator to propose additions

---

## D

### Due
**中文**: 應付款項
**定義**: 群眾集資專案中，一筆從平台應付給特定對象的款項記錄。Due 記錄了金額、付款對象、付款狀態等資訊，是 TaxInfo 計算所得的基礎資料來源。
**類型**: Entity
**相關 Entity/Component**: Payment, TaxInfo
**業務規則**: CR-001 (Export Payment Status Filter), CR-003 (Due-Payment Cardinality)
**範例**: 一筆群募專案結束後，平台需支付給提案者的款項

**注意事項**:
- Due 與 Payment 在 success 狀態下等效 1:1 關係
- 匯出所得時僅取 payment status = success 的 Due

**相關詞彙**: Payment, TaxInfo

---

## I

### IdentityNumber
**中文**: 身分統一編號
**定義**: 用於所得稅申報的身分識別碼，優先取統一編號（vat_id），若無則取身分證字號（id_number）。計算邏輯為 COALESCE(vat_id, id_number)。
**類型**: Value Object
**業務規則**: CA-002 (IdentityNumber Resolution)
**範例**: 公司法人使用統一編號 12345678；自然人使用身分證字號 A123456789

**注意事項**:
- 優先序：vat_id > id_number
- 兩者皆無時為空值，需注意資料完整性

**相關詞彙**: TaxInfo, TaxInfoDetail

---

### IncomeMethod
**中文**: 所得類別
**定義**: 標記一筆所得的來源類型，用於稅務申報分類。屋主固定為 lease_income（租賃所得），一般用戶則依據 unchanged_contract_programs 判斷。
**類型**: Value Object
**業務規則**: CA-001 (IncomeMethod Determination)
**範例**: 屋主的太陽能板租金所得為 lease_income；一般集資回饋所得依合約方案判定

**注意事項**:
- 屋主身份的判定來自 Roof::Owner 上游
- unchanged_contract_programs 定義了哪些合約方案對應哪種所得類別

**相關詞彙**: TaxInfo, RoofOwnerUnifiedIncomes

---

### IncomeMonth
**中文**: 所得月份（民國格式）
**定義**: 所得發生的月份，以民國年格式表示。轉換公式為：西元年減 1911 後加上月份。例如 2025 年 3 月表示為 11403。
**類型**: Value Object
**業務規則**: CA-003 (IncomeMonth Conversion)
**範例**: 2025-03 轉換為 11403（114 年 3 月）

**注意事項**:
- 格式為 YYYMM，其中 YYY 為民國年（可能為 3 位數）
- 用於對接政府稅務系統

**相關詞彙**: TaxInfo, TaxInfoDetail

---

## O

### OtherIncome
**中文**: 其他所得
**定義**: 非屋主租賃所得的其他類型所得，來自一般群眾集資的回饋或分潤。屬於 TaxInfo 匯出時的所得分類之一。
**類型**: Concept
**相關 Entity/Component**: TaxInfo, TaxInfoDetail
**範例**: 一般贊助者從集資專案獲得的現金回饋所得

**相關詞彙**: IncomeMethod, RoofOwnerUnifiedIncomes

---

## P

### Payment
**中文**: 付款記錄
**定義**: Due 的實際付款執行記錄，包含付款狀態（success/failed 等）。在所得匯出時，僅 success 狀態的 Payment 會被納入計算。
**類型**: Entity
**相關 Entity/Component**: Due, TaxInfo
**業務規則**: CR-001 (Export Payment Status Filter), CR-003 (Due-Payment Cardinality)
**範例**: 一筆 Due 對應的匯款執行成功記錄

**注意事項**:
- 匯出所得時以 payment status = success 為過濾條件
- RoofRentalAccount 的 Payment 不受此過濾規則限制（CR-002）

**相關詞彙**: Due, RoofRentalAccount

---

## R

### RoofOwnerUnifiedIncomes
**中文**: 屋主統整所得
**定義**: 將屋主身份的所有租賃所得統整歸戶的彙總資料。屋主可能同時擁有租賃所得（來自太陽能板）和其他所得（來自集資參與），此概念將其統一管理。
**類型**: Concept
**相關 Entity/Component**: TaxInfo, RoofRentalAccount
**範例**: 某屋主同時有 3 筆太陽能板租金所得和 1 筆集資回饋所得，統整為該屋主的年度所得清單

**相關詞彙**: RoofRentalAccount, IncomeMethod, OtherIncome

---

### RoofRentalAccount
**中文**: 屋頂租賃帳戶
**定義**: 太陽能板屋頂出租者的租金帳戶，記錄屋主的租賃收入。此帳戶的付款記錄不受一般 Payment status 過濾規則限制。
**類型**: Entity
**業務規則**: CR-002 (RoofRental Bypass Payment Filter)
**範例**: 屋主出租屋頂安裝太陽能板，每月收取的租金記錄

**注意事項**:
- 此帳戶的所得類別固定為 lease_income
- 不受 CR-001 的 success 過濾限制

**相關詞彙**: RoofOwnerUnifiedIncomes, IncomeMethod

---

## T

### TaxInfo
**中文**: 所得稅申報資料
**定義**: 管理群眾集資平台所得稅申報所需的完整資料，包含所得人身份、所得金額、所得類別等。支援批次上傳、XLSX 匯出和清單管理等功能。
**類型**: Aggregate
**相關 Entity/Component**: TaxInfoDetail, Due, Payment
**業務規則**: CA-001, CA-002, CA-003, CR-001, CR-002, CR-003
**範例**: 年度結算時，匯出所有成功付款的所得資料供稅務申報

**注意事項**:
- 匯出功能和清單功能是不同的查詢視角，匯出有額外過濾條件
- 屋主和一般用戶的所得計算邏輯不同

**相關詞彙**: TaxInfoDetail, Due, Payment, IncomeMethod

---

### TaxInfoDetail
**中文**: 所得稅申報明細
**定義**: TaxInfo 的明細項目，記錄單筆所得的具體資訊，包含所得人、所得金額、所得月份、所得類別等欄位。
**類型**: Entity
**所屬 Aggregate**: TaxInfo
**相關 Entity/Component**: TaxInfo, IdentityNumber, IncomeMonth, IncomeMethod
**範例**: 某贊助者在 2025 年 3 月獲得的一筆 5000 元回饋所得明細

**相關詞彙**: TaxInfo, IdentityNumber, IncomeMonth, IncomeMethod

---

## Maintenance Log

| Date | Change | Changed By |
|------|--------|------------|
| 2026-04-07 | Initial UL created with 10 terms: Due, Payment, TaxInfo, TaxInfoDetail, IncomeMethod, IdentityNumber, IncomeMonth, RoofRentalAccount, RoofOwnerUnifiedIncomes, OtherIncome | curator |
