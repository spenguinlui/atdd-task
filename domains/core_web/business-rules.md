# core_web Business Rules (核心業務規則)

> **Purpose**: Document core business rules and constraints that govern core_web Crowdfund::TaxInfo domain. These rules are domain-invariants that must always be enforced.

**Last Updated**: 2026-04-07
**Maintained By**: Development Team + atdd-knowledge-curator

---

## How to Use This Document

- **For Developers**: Reference when implementing business logic
- **For AI Agents**: Load to understand constraints before code generation
- **For Testing**: Use as source for test case generation
- **For Updates**: Use atdd-knowledge-curator to propose new rules

---

## Rule Categories

### 4. Calculation Rules (計算規則)

#### Rule: IncomeMethod Determination
**ID**: `CA-001`
**Domain**: Crowdfund::TaxInfo
**Description**: 決定一筆所得的所得類別（IncomeMethod）。屋主身份固定為 lease_income（租賃所得），一般用戶則依據 unchanged_contract_programs 配置判斷所得類別。

**Formula**:
```
if user is RoofOwner:
    income_method = "lease_income"
else:
    income_method = determine_by(unchanged_contract_programs)
```

**Inputs**:
- user_type: 用戶身份（屋主 or 一般用戶）
- unchanged_contract_programs: 合約方案配置表

**Output**:
- income_method: 所得類別字串

**Edge Cases**:
- 屋主同時參與一般集資：屋主身份的所得為 lease_income，一般集資所得另行判定

**Examples**:
```
Input: user_type = RoofOwner
Output: income_method = "lease_income"

Input: user_type = GeneralUser, contract_program = "xxx"
Output: income_method = determined by unchanged_contract_programs mapping
```

**Related Rules**: CR-002

---

#### Rule: IdentityNumber Resolution
**ID**: `CA-002`
**Domain**: Crowdfund::TaxInfo
**Description**: 解析所得人的身分識別碼。優先使用統一編號（vat_id），若無統一編號則使用身分證字號（id_number）。

**Formula**:
```sql
COALESCE(vat_id, id_number)
```

**Inputs**:
- vat_id: 統一編號（法人適用，可為 NULL）
- id_number: 身分證字號（自然人適用，可為 NULL）

**Output**:
- identity_number: 用於申報的身分識別碼

**Edge Cases**:
- 兩者皆有值：使用 vat_id
- 兩者皆為 NULL：回傳 NULL，需注意資料完整性檢查

**Examples**:
```
Input: vat_id = "12345678", id_number = "A123456789"
Output: "12345678" (使用 vat_id)

Input: vat_id = NULL, id_number = "A123456789"
Output: "A123456789" (fallback 到 id_number)
```

---

#### Rule: IncomeMonth Conversion
**ID**: `CA-003`
**Domain**: Crowdfund::TaxInfo
**Description**: 將西元年月轉換為民國年月格式，用於對接政府稅務系統。轉換公式為西元年減 1911 後串接月份。

**Formula**:
```
income_month = (western_year - 1911) * 100 + month
# 或等效字串：sprintf("%d%02d", western_year - 1911, month)
```

**Inputs**:
- western_year: 西元年（整數）
- month: 月份（1-12）

**Output**:
- income_month: 民國年月（整數，格式 YYYMM）

**Precision**: 整數，無小數

**Edge Cases**:
- 跨年：2025-01 = 11401，2025-12 = 11412
- 民國年為 3 位數：2025 年 = 114 年

**Examples**:
```
Input: western_year = 2025, month = 3
Calculation: (2025 - 1911) * 100 + 3 = 114 * 100 + 3 = 11403
Output: 11403

Input: western_year = 2025, month = 12
Calculation: (2025 - 1911) * 100 + 12 = 11412
Output: 11412
```

---

### 2. Constraint Rules (約束條件規則)

#### Rule: Export Payment Status Filter
**ID**: `CR-001`
**Domain**: Crowdfund::TaxInfo
**Description**: 匯出所得資料時，僅包含付款狀態為 success 的記錄。非成功狀態的付款（failed、pending 等）不納入所得計算。

**Constraint Type**: Dependency

**Validation Logic**:
```ruby
# 匯出查詢時的過濾條件
WHERE payment.status = 'success'
```

**Exceptions**: RoofRentalAccount 不受此規則限制（見 CR-002）

**Examples**:
```
OK: payment.status = "success" -> 納入匯出
NG: payment.status = "failed" -> 排除
NG: payment.status = "pending" -> 排除
```

**Related Rules**: CR-002, CR-003

---

#### Rule: RoofRental Bypass Payment Filter
**ID**: `CR-002`
**Domain**: Crowdfund::TaxInfo
**Description**: RoofRentalAccount（屋頂租賃帳戶）的所得資料不受 CR-001 的 payment status = success 過濾條件限制。屋頂租賃所得有獨立的資料來源和處理邏輯。

**Constraint Type**: Dependency

**Validation Logic**:
```ruby
# RoofRentalAccount 的所得直接納入，不檢查 payment status
if source == RoofRentalAccount
  # bypass payment status filter
  include_in_export
end
```

**Exceptions**: 僅適用於 RoofRentalAccount，其他來源仍受 CR-001 約束

**Examples**:
```
OK: RoofRentalAccount 的租金所得 -> 直接納入匯出（不論 payment status）
NG: 一般 Due 的 payment.status = "failed" -> 仍被 CR-001 排除
```

**Related Rules**: CR-001, CA-001

---

#### Rule: Due-Payment Cardinality
**ID**: `CR-003`
**Domain**: Crowdfund::TaxInfo
**Description**: 在 payment status = success 的條件下，Due 與 Payment 等效為 1:1 關係。每筆成功的 Due 對應恰好一筆成功的 Payment。

**Constraint Type**: Cardinality

**Validation Logic**:
```sql
-- 在 success 狀態下，一筆 Due 只有一筆 Payment
SELECT due_id, COUNT(*) as payment_count
FROM payments
WHERE status = 'success'
GROUP BY due_id
HAVING COUNT(*) > 1  -- 不應出現
```

**Exceptions**: 無

**Examples**:
```
OK: Due#1 -> Payment#1 (status=success) -- 1:1
NG: Due#1 -> Payment#1 (success) + Payment#2 (success) -- 不應出現重複成功
OK: Due#1 -> Payment#1 (failed) + Payment#2 (success) -- 只有一筆 success，等效 1:1
```

**Related Rules**: CR-001

---

## Maintenance Log

| Date | Rule ID | Change | Changed By |
|------|---------|--------|------------|
| 2026-04-07 | - | Initial business rules created with 6 rules: CA-001, CA-002, CA-003, CR-001, CR-002, CR-003 | curator |
