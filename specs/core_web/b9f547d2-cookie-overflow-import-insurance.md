# 批次匯入保險 CookieOverflow 修復

> 任務 ID：b9f547d2-ae6b-453d-8597-4d3ba21701cd
> 專案：core_web
> 建立日期：2026-04-10

## Business Context

**Why**: 批次匯入保險時，大量驗證錯誤導致 flash 訊息超過 cookie 4KB 限制，觸發 CookieOverflow 系統錯誤，使用者無法得知錯誤原因
**Who**: 後台管理人員（電費會計）
**Impact**: 匯入功能在有大量錯誤資料時完全無法使用

## Domain

- **主要 Domain**：ElectricityAccounting::FixedCharge
- **相關 Domains**：無

## ATDD Profile

- **Type**：integration
- **Reason**：檔案上傳後的後端處理邏輯，需驗證 flash 訊息截斷行為，無法單純從畫面即時驗證截斷邏輯的正確性（需檢查 flash 大小），且涉及 UseCase 層與 Controller 層的整合
- **Executor**：rspec

## Acceptance Criteria

- [ ] 上傳含 50 行全部格式錯誤的 xlsx 時，不拋出 CookieOverflow，頁面正常 redirect
- [ ] 錯誤訊息顯示前 10 筆具體錯誤內容
- [ ] 超過 10 筆錯誤時，末尾顯示總錯誤數摘要
- [ ] 少於或等於 10 筆錯誤時，完整顯示所有錯誤（行為不變）
- [ ] 正常檔案匯入成功的流程不受影響

## Scenarios

### Scenario 1: 大量錯誤不觸發 CookieOverflow（Happy Path for Fix）

**Given** 一個 xlsx 檔案包含 50 行資料，每行的案場名稱都是不存在的 `"不存在的案場"`
**When** 使用者在「批次建立保險」頁面上傳此檔案
**Then** 頁面正常 redirect 回新增頁面，不拋出 `CookieOverflow`
**And** flash alert 包含前 10 筆錯誤：`"第 2 行：案場名稱找不到"`、`"第 3 行：案場名稱找不到"` ... `"第 11 行：案場名稱找不到"`
**And** flash alert 末尾顯示 `"...等，共 50 筆錯誤，請修正後重新上傳"`

### Scenario 2: 少量錯誤完整顯示（行為不變）

**Given** 一個 xlsx 檔案包含 3 行資料，第 1 行案場名稱為空、第 2 行保險類別為 `"不合法類別"`、第 3 行金額為 `0`
**When** 使用者上傳此檔案
**Then** flash alert 完整顯示 3 筆錯誤：
  - `"第 2 行：案場名稱不可為空"`
  - `"第 3 行：保險類別不合法（請填寫「電子設備保險」或「公共意外責任險」）"`
  - `"第 4 行：金額必須為正數"`
**And** 不顯示摘要文字

### Scenario 3: 正好 10 筆錯誤不顯示摘要

**Given** 一個 xlsx 檔案包含 10 行資料，每行的案場名稱都是不存在的
**When** 使用者上傳此檔案
**Then** flash alert 完整顯示 10 筆錯誤
**And** 不顯示 `"...等，共 N 筆錯誤"` 摘要文字

### Scenario 4: 11 筆錯誤開始顯示摘要

**Given** 一個 xlsx 檔案包含 11 行資料，每行的案場名稱都是不存在的
**When** 使用者上傳此檔案
**Then** flash alert 顯示前 10 筆錯誤
**And** flash alert 末尾顯示 `"...等，共 11 筆錯誤，請修正後重新上傳"`

### Scenario 5: 正常匯入不受影響

**Given** 一個 xlsx 檔案包含 5 行有效資料（案場存在、類別正確、日期合法、金額為正整數）
**When** 使用者上傳此檔案
**Then** 匯入成功，flash notice 顯示 `"成功建立 5 筆保險"`
**And** 頁面 redirect 到固定費用列表頁

### Scenario 6: 每行多個欄位錯誤時的截斷

**Given** 一個 xlsx 檔案包含 20 行資料，每行的案場名稱為空、保險類別為空、金額為空（每行產生 3 筆錯誤，共 60 筆錯誤）
**When** 使用者上傳此檔案
**Then** flash alert 顯示前 10 筆錯誤（包含第 2 行的 3 筆錯誤 + 第 3 行的 3 筆錯誤 + 第 4 行的 3 筆錯誤 + 第 5 行的 1 筆錯誤）
**And** flash alert 末尾顯示 `"...等，共 60 筆錯誤，請修正後重新上傳"`

## Technical Notes

- 問題在 Controller 的 `import_xlsx` action 第 71 行：`flash[:alert] = Array(result[:errors]).join("\n")`
- `ImportInsuranceXlsx#validate_rows` 每行最多產生 6 種驗證錯誤
- Rails cookie 上限 4KB，中文字元經 URL encoding 膨脹約 3 倍
- 截斷邏輯應在 Controller 層處理（UseCase 仍回傳完整錯誤，Controller 負責截斷後存入 flash）
- 截斷閾值建議 10 筆錯誤（經驗值：10 筆中文錯誤 ~800 bytes，加上其他 cookie 內容仍在安全範圍）

## Verification Notes

- **Test Helpers**：無特殊需求
- **Special Considerations**：測試需模擬大量行數的 xlsx 檔案，可用 mock 或 factory 建立含多行資料的檔案
- **Data Boundary Check**：None
