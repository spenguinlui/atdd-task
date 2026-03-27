# {Feature Name}

> 任務 ID：{task_id}
> 專案：{project}
> 建立日期：{date}

## Business Context

**Why**: {為什麼要做這個功能}
**Who**: {目標使用者}
**Impact**: {預期影響}

## Domain

- **主要 Domain**：{domain}
- **相關 Domains**：{related_domains}

## ATDD Profile

- **Type**：{e2e / integration / unit}
- **Reason**：{選擇此 profile 的原因}
- **Executor**：{chrome-mcp / rspec / jest}

## Acceptance Criteria

驗收標準（業務結果導向）：

- [ ] {Criterion 1 - 使用者可以...}
- [ ] {Criterion 2 - 系統應該...}
- [ ] {Criterion 3 - 結果必須...}

## Scenarios

### Scenario 1: {Happy Path 標題}

**Given** {前置條件}
**When** {使用者動作}
**Then** {預期結果}

### Scenario 2: {Alternative Path 標題}

**Given** {前置條件}
**When** {使用者動作}
**Then** {預期結果}

### Scenario 3: {Error Path 標題}

**Given** {前置條件}
**When** {錯誤操作}
**Then** {錯誤處理}

## Technical Notes

{實作注意事項、技術限制、相依性說明}

## Verification Notes

- **Test Helpers**：{time / mock / async helpers if needed}
- **Special Considerations**：{給 tester 的注意事項}
- **Data Boundary Check**：{None / Required — 若為 Required，列出需確認的 model 組合及確認重點（如日期粒度、數量關係）}
